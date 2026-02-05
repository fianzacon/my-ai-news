"""
STEP 2: Category filtering using LLM to classify articles as PASS/FAIL.
"""
import logging
import json
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_google_genai import ChatGoogleGenerativeAI

from .models import NewsArticle, CategoryFilterResult
from .config import PipelineConfig, RateLimiter

logger = logging.getLogger(__name__)


class CategoryFilter:
    """LLM-based category filtering to determine if articles pass or fail."""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=PipelineConfig.LLM_MODEL,
            temperature=PipelineConfig.LLM_TEMPERATURE
        )
        self.rate_limiter = RateLimiter(PipelineConfig.LLM_REQUESTS_PER_MINUTE)
    
    def filter_articles(self, articles: List[NewsArticle]) -> List[CategoryFilterResult]:
        """
        Filter articles by category relevance (with parallel processing).
        
        Args:
            articles: List of articles to filter
            
        Returns:
            List of CategoryFilterResult objects (only passed articles)
        """
        logger.info("\n" + "=" * 60)
        logger.info("STEP 2: CATEGORY FILTERING (PASS / FAIL ONLY)")
        logger.info(f"Processing {len(articles)} articles in parallel...")
        logger.info("=" * 60)
        
        results = []
        passed_count = 0
        regulatory_count = 0
        processed_count = 0
        
        # Parallel processing with ThreadPoolExecutor
        max_workers = min(10, PipelineConfig.LLM_REQUESTS_PER_MINUTE // 6)  # Conservative
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_article = {
                executor.submit(self._classify_article_safe, article, i): (article, i) 
                for i, article in enumerate(articles, 1)
            }
            
            # Process completed tasks
            for future in as_completed(future_to_article):
                article, idx = future_to_article[future]
                processed_count += 1
                
                try:
                    result = future.result()
                    
                    if result.passed:
                        passed_count += 1
                        results.append(result)
                        logger.info(f"[{processed_count}/{len(articles)}] ✅ {article.title[:50]}... - {', '.join(result.categories)}")
                        
                        if result.must_keep_for_regulation():
                            regulatory_count += 1
                    else:
                        logger.info(f"[{processed_count}/{len(articles)}] ❌ {article.title[:50]}... - {result.reason[:30]}")
                        
                except Exception as e:
                    logger.error(f"[{processed_count}/{len(articles)}] ⚠️  Error: {article.title[:50]}... - {e}")
                    # Default to pass on error
                    result = CategoryFilterResult(
                        article=article,
                        passed=True,
                        categories=['technology'],
                        reason="Error during classification, passed by default"
                    )
                    results.append(result)
                    passed_count += 1
        
        logger.info(f"\n✅ Category filtering complete:")
        logger.info(f"   Passed: {passed_count}/{len(articles)}")
        logger.info(f"   Regulatory articles: {regulatory_count}")
        
        return results
    
    def _classify_article_safe(self, article: NewsArticle, idx: int) -> CategoryFilterResult:
        """Thread-safe wrapper for _classify_article."""
        try:
            return self._classify_article(article)
        except Exception as e:
            logger.error(f"Classification error for article {idx}: {e}")
            return CategoryFilterResult(
                article=article,
                passed=True,
                categories=['technology'],
                reason="Error, defaulted to pass"
            )
    
    def _classify_article(self, article: NewsArticle) -> CategoryFilterResult:
        """
        Classify a single article using LLM.
        
        Args:
            article: Article to classify
            
        Returns:
            CategoryFilterResult with pass/fail decision
        """
        prompt = self._build_classification_prompt(article)
        
        try:
            # Apply rate limiting before making API call
            self.rate_limiter.wait_if_needed()
            
            response = self.llm.invoke(prompt).content
            parsed = self._parse_llm_response(response)
            
            return CategoryFilterResult(
                article=article,
                passed=parsed['pass'],
                categories=parsed['categories'],
                reason=parsed['reason']
            )
            
        except Exception as e:
            logger.error(f"LLM classification error: {e}")
            # Default to pass if LLM fails
            return CategoryFilterResult(
                article=article,
                passed=True,
                categories=['technology'],
                reason="LLM error, defaulted to pass"
            )
    
    def _build_classification_prompt(self, article: NewsArticle) -> str:
        """Build the prompt for LLM classification."""
        
        content = article.lead_paragraph or article.title
        
        prompt = f"""You are a news classification AI for Lotte Members advertising/marketing team.

Analyze the following article and decide if it should PASS or FAIL.

**Article Title:** {article.title}
**Article Lead:** {content}
**Source:** {article.media_name or article.source}

**CRITICAL RULE - AI MUST BE THE MAIN TOPIC:**

Article must explicitly mention AI-related terms AND discuss them as the core subject:
- "AI", "인공지능", "머신러닝", "딥러닝", "GPT", "LLM", "생성AI", "챗봇", "Chatbot"
- "자연어처리", "NLP", "컴퓨터비전", "음성인식", "Claude", "Gemini", "ChatGPT"

**PASS ONLY IF article matches ONE of these categories:**

1. **solution** - AI 마케팅/광고 도구 또는 서비스
   - AI 기반 고객 분석, 타겟팅, 개인화, CRM, 광고 플랫폼

2. **case** - 기업의 AI 도입 사례
   - 실제 기업이 AI를 마케팅/광고/고객서비스에 적용한 구체적 사례
   - 성공/실패 사례, 효과 측정 포함

3. **technology** - AI 기술 자체
   - AI 모델, 알고리즘, 데이터 분석 기술
   - 마케팅 직접 관련 없어도 향후 적용 가능성 있으면 포함

4. **regulation** - AI 규제/법률 ⚠️ 절대 제외 금지
   - AI 관련 법률, 개인정보보호, 데이터 규제, AI 윤리 가이드라인

**IMMEDIATELY FAIL IF:**
❌ AI 키워드가 제목/리드에 없음
❌ 지역 축제, 문화 행사, 관광 (AI 기술 활용 명시 없음)
❌ 무역/관세/정치 뉴스 (AI 산업 영향 언급 없음)
❌ 인사 발령, 임원 선임 (AI 기업/직무 아님)
❌ 일반 기업 뉴스 (IPO, 실적, 증자) - AI 제품 설명 없음
❌ 스포츠, 연예, 날씨, 사건/사고
❌ 단순 "디지털 전환", "혁신", "스마트" 언급 (AI 구체적 설명 없음)

**Examples:**
✅ PASS: "네이버, GPT 기반 AI 검색 출시" → technology
✅ PASS: "현대카드, AI 추천으로 매출 20% 증가" → case
✅ PASS: "EU AI Act 시행, 기업 대응 방안" → regulation
❌ FAIL: "논산딸기축제, 문화관광축제 선정" → AI 무관
❌ FAIL: "트럼프 관세 25% 인상" → AI 무관
❌ FAIL: "박 교수, 학술지 편집장 선임" → AI 무관

**Output Format (JSON):**
{{
  "pass": true/false,
  "categories": ["solution", "case", "technology", "regulation"],
  "reason": "brief explanation in Korean"
}}

Respond ONLY with valid JSON, no additional text."""
        
        return prompt
    
    def _parse_llm_response(self, response: str) -> dict:
        """
        Parse LLM JSON response.
        
        Args:
            response: LLM response string
            
        Returns:
            Dict with 'pass', 'categories', 'reason'
        """
        try:
            # Extract JSON from response (in case there's extra text)
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                parsed = json.loads(json_str)
            else:
                parsed = json.loads(response)
            
            # Validate structure
            if 'pass' not in parsed or 'categories' not in parsed or 'reason' not in parsed:
                raise ValueError("Missing required fields in LLM response")
            
            # Ensure pass is boolean
            if isinstance(parsed['pass'], str):
                parsed['pass'] = parsed['pass'].lower() in ['true', 'yes', '1']
            
            # Ensure categories is a list
            if isinstance(parsed['categories'], str):
                parsed['categories'] = [parsed['categories']]
            
            # Validate category values
            valid_categories = ['solution', 'case', 'technology', 'regulation']
            parsed['categories'] = [
                cat for cat in parsed['categories'] 
                if cat in valid_categories
            ]
            
            # If regulation is present, must pass
            if 'regulation' in parsed['categories']:
                parsed['pass'] = True
            
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            logger.error(f"Response was: {response}")
            # Default to pass with technology category
            return {
                'pass': True,
                'categories': ['technology'],
                'reason': 'JSON parsing error, defaulted to pass'
            }
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return {
                'pass': True,
                'categories': ['technology'],
                'reason': 'Error parsing response, defaulted to pass'
            }
