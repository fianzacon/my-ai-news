"""
STEP 4 & 5: Value validation and Lotte Members context analysis.
"""
import logging
import json
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_google_genai import ChatGoogleGenerativeAI

from .models import CategoryFilterResult, ValueValidationResult, LotteContextAnalysis
from .config import PipelineConfig, RateLimiter

logger = logging.getLogger(__name__)


class BusinessAnalyzer:
    """Validate business value and analyze Lotte Members context."""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=PipelineConfig.LLM_MODEL,
            temperature=PipelineConfig.LLM_TEMPERATURE
        )
        self.rate_limiter = RateLimiter(PipelineConfig.LLM_REQUESTS_PER_MINUTE)
    
    def validate_and_analyze(
        self, 
        results: List[CategoryFilterResult]
    ) -> List[LotteContextAnalysis]:
        """
        Validate business value (Step 4) and analyze Lotte context (Step 5).
        
        Args:
            results: Articles that passed content deduplication
            
        Returns:
            List of articles with Lotte context analysis (only those with business value)
        """
        logger.info("\n" + "=" * 60)
        logger.info("STEP 4: VALUE VALIDATION (BUSINESS RELEVANCE CHECK)")
        logger.info("=" * 60)
        
        # Step 4: Value validation
        validated = self._validate_business_value(results)
        
        logger.info("\n" + "=" * 60)
        logger.info("STEP 5: LOTTE MEMBERS CONTEXT INTERPRETATION")
        logger.info("=" * 60)
        
        # Step 5: Lotte context analysis
        analyzed = self._analyze_lotte_context(validated)
        
        return analyzed
    
    def _validate_business_value(
        self, 
        results: List[CategoryFilterResult]
    ) -> List[ValueValidationResult]:
        """
        Validate if articles have real business value (with parallel processing).
        
        Args:
            results: Articles to validate
            
        Returns:
            List of validated articles (only those with business value)
        """
        logger.info(f"Processing {len(results)} articles in parallel...")
        
        validated = []
        passed_count = 0
        regulatory_retained = 0
        processed_count = 0
        
        # Parallel processing
        max_workers = min(10, PipelineConfig.LLM_REQUESTS_PER_MINUTE // 6)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_result = {
                executor.submit(self._validate_single_article, result): result 
                for result in results
            }
            
            for future in as_completed(future_to_result):
                result = future_to_result[future]
                processed_count += 1
                
                try:
                    validation = future.result()
                    
                    if validation.has_business_value:
                        validated.append(validation)
                        passed_count += 1
                        logger.info(f"[{processed_count}/{len(results)}] ✅ {result.article.title[:50]}...")
                        
                        if validation.is_regulatory:
                            regulatory_retained += 1
                    else:
                        logger.info(f"[{processed_count}/{len(results)}] ❌ {result.article.title[:50]}...")
                        
                except Exception as e:
                    logger.error(f"[{processed_count}/{len(results)}] ⚠️  Error: {e}")
                    validation = ValueValidationResult(
                        article=result.article,
                        has_business_value=True,
                        reason="Error, kept by default",
                        is_regulatory=result.must_keep_for_regulation()
                    )
                    validated.append(validation)
                    passed_count += 1
        
        logger.info(f"\n✅ Value validation complete:")
        logger.info(f"   Has business value: {passed_count}/{len(results)}")
        logger.info(f"   Regulatory retained: {regulatory_retained}")
        
        return validated
    
    def _validate_single_article(
        self, 
        result: CategoryFilterResult
    ) -> ValueValidationResult:
        """
        Validate business value for a single article.
        
        Args:
            result: Article to validate
            
        Returns:
            ValueValidationResult
        """
        is_regulatory = result.must_keep_for_regulation()
        
        prompt = f"""You are analyzing news for an advertising/marketing data company (Lotte Members).

Read the following article and determine if it has REAL VALUE for advertising/marketing practitioners.

**Title:** {result.article.title}
**Categories:** {', '.join(result.categories)}
**Content:** {result.article.full_content[:1500]}...

**CRITICAL RULES - AI MUST BE EXPLICIT:**

Article must explicitly mention AI-related terms:
- "AI", "인공지능", "머신러닝", "딥러닝", "GPT", "LLM", "생성AI", "챗봇", "Chatbot"
- "자연어처리", "NLP", "컴퓨터비전", "음성인식", "추천 알고리즘"

**KEEP ONLY IF:**
- AI 기술/제품/서비스가 핵심 주제 (단순 언급이 아닌 주요 내용)
- AI 규제/법률 (regulation 카테고리는 항상 유지)
- AI 마케팅/광고 도구의 구체적 사례 (실제 적용 사례, 효과 등)

**IMMEDIATELY FAIL IF:**
- ❌ 지역 축제, 문화 행사, 관광 (AI 기술 활용 명시 없으면)
- ❌ 무역/관세/정치 뉴스 (AI 산업에 대한 구체적 영향 분석 없으면)
- ❌ 인사 발령, 임원 선임, 수상 소식 (AI 기업이 아니거나 AI 직무가 아니면)
- ❌ 일반 기업 뉴스 (M&A, IPO, 실적, 증자) - AI 제품/서비스 구체적 설명 없으면
- ❌ 스포츠, 연예, 날씨, 사건/사고
- ❌ 단순 "디지털 전환", "혁신", "스마트" 언급만 있고 AI 기술 설명 없음

**ALWAYS KEEP (override above):**
- ✅ Regulatory/legal articles about AI (AI Act, AI 윤리, AI 관련 개인정보보호법)

**Examples:**
✅ KEEP: "네이버, GPT-4 기반 검색 AI '큐' 출시" → AI 제품 명시
✅ KEEP: "EU AI Act 시행, 국내 기업 대응 방안" → AI 규제
❌ FAIL: "논산딸기축제, 문화관광축제 선정" → AI 무관
❌ FAIL: "트럼프 관세 25% 인상" → AI 산업 영향 분석 없음
❌ FAIL: "박 교수, 학술지 편집장 선임" → AI 기업/직무 아님

**Output Format (JSON):**
{{
  "has_business_value": true/false,
  "reason": "brief explanation in Korean (AI 언급 여부 명시)"
}}

Respond ONLY with valid JSON, no additional text."""
        
        try:
            # Apply rate limiting
            self.rate_limiter.wait_if_needed()
            
            response = self.llm.invoke(prompt).content
            parsed = self._parse_validation_response(response)
            
            # If it's regulatory, override to keep it unless explicitly irrelevant
            if is_regulatory and parsed['has_business_value'] == False:
                logger.warning("   ⚠️  Regulatory article marked as no value, overriding to keep")
                parsed['has_business_value'] = True
                parsed['reason'] = f"Regulatory article retained. Original: {parsed['reason']}"
            
            return ValueValidationResult(
                article=result.article,
                has_business_value=parsed['has_business_value'],
                reason=parsed['reason'],
                is_regulatory=is_regulatory
            )
            
        except Exception as e:
            logger.error(f"Value validation error: {e}")
            return ValueValidationResult(
                article=result.article,
                has_business_value=True,
                reason="Error during validation, kept by default",
                is_regulatory=is_regulatory
            )
    
    def _analyze_lotte_context(
        self, 
        validated: List[ValueValidationResult]
    ) -> List[LotteContextAnalysis]:
        """
        Analyze articles in Lotte Members business context (with parallel processing).
        
        Args:
            validated: Articles with business value
            
        Returns:
            List of articles with Lotte context analysis
        """
        logger.info(f"Processing {len(validated)} articles in parallel...")
        
        analyzed = []
        processed_count = 0
        
        # Parallel processing
        max_workers = min(10, PipelineConfig.LLM_REQUESTS_PER_MINUTE // 6)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_validation = {
                executor.submit(self._analyze_single_article, validation): validation 
                for validation in validated
            }
            
            for future in as_completed(future_to_validation):
                validation = future_to_validation[future]
                processed_count += 1
                
                try:
                    analysis = future.result()
                    analyzed.append(analysis)
                    logger.info(f"[{processed_count}/{len(validated)}] 🎯 {validation.article.title[:50]}... - {analysis.impact_type}")
                    
                except Exception as e:
                    logger.error(f"[{processed_count}/{len(validated)}] ⚠️  Error: {e}")
                    # Create default analysis
                    analysis = LotteContextAnalysis(
                        article=validation.article,
                        impact_type='watchlist',
                        impact_areas=['none'],
                        reasoning="Error during analysis"
                    )
                    analyzed.append(analysis)
        
        logger.info(f"\n✅ Lotte context analysis complete: {len(analyzed)} articles")
        
        return analyzed
    
    def _analyze_single_article(
        self, 
        validation: ValueValidationResult
    ) -> LotteContextAnalysis:
        """
        Analyze Lotte Members context for a single article.
        
        Args:
            validation: Validated article
            
        Returns:
            LotteContextAnalysis
        """
        prompt = f"""You are a strategic analyst for Lotte Members, an advertising & data business.

Analyze this AI news article from a Lotte Members business perspective.

**Title:** {validation.article.title}
**Content:** {validation.article.full_content[:2000]}...

**Context:** Lotte Members operates:
- Membership data platform (30M+ members)
- Advertising agency services
- Data sales business
- Online-offline retail linkage

**Analysis Required:**

1. **Industry Relevance** (choose ONE) - BE VERY STRICT:
   
   **direct (직접 연관)**: 롯데멤버스가 **내일부터 바로 적용/활용 가능**한 정보만 선택
   ✅ 포함: 광고/마케팅 플랫폼 기술, 고객 데이터 분석 도구, 타겟팅 솔루션, 
           멤버십/리테일 CRM, 커머스 추천 시스템, 온오프라인 통합 마케팅, 
           동일 사업 영역의 경쟁사 움직임
   ❌ 제외: 타 산업 사례(금융/보험/여행/의료), AI 기술 일반론, 인프라 투자 소식,
           M&A/정책 뉴스, 하드웨어 제품, B2B 솔루션, 교육/창업 프로그램
   
   **indirect (간접 연관)**: 참고용 (위에서 제외된 모든 기사)

2. **Industry Category** (if indirect):
   - healthcare: 의료, 헬스케어
   - manufacturing: 제조, 생산
   - robotics: 로봇, 자율주행
   - energy: 에너지, 전력
   - finance: 금융, 보험
   - travel: 여행, 관광
   - education: 교육, 창업 지원
   - infrastructure: 인프라, 투자
   - general-ai: 범용 AI 기술 (산업 미지정)
   - other: 기타

3. **Impact Type** (choose ONE):
   - opportunity: Clear business opportunity or advantage
   - threat: Competitive threat or risk
   - mixed: Both opportunities and threats
   - watchlist: Important to monitor, unclear impact

4. **Impact Areas** (can be MULTIPLE):
   - membership data usage: How we collect, use, analyze member data
   - targeting / segmentation: Customer targeting and segmentation capabilities
   - advertising agency / data sales business: Our core advertising/data sales services
   - online–offline linkage: Connecting online and offline customer experiences
   - legal / compliance: Regulatory compliance and legal risks
   - none: No specific impact area

5. **One-sentence reasoning:** Why this matters to Lotte Members

**Output Format (JSON):**
{{
  "industry_relevance": "direct|indirect",
  "industry_category": "retail-marketing|healthcare|manufacturing|robotics|energy|general-ai|other",
  "impact_type": "opportunity|threat|mixed|watchlist",
  "impact_areas": ["membership data usage", "targeting / segmentation", ...],
  "reasoning": "one-sentence Korean explanation"
}}

Respond ONLY with valid JSON, no additional text."""
        
        try:
            # Apply rate limiting
            self.rate_limiter.wait_if_needed()
            
            response = self.llm.invoke(prompt).content
            parsed = self._parse_analysis_response(response)
            
            return LotteContextAnalysis(
                article=validation.article,
                impact_type=parsed['impact_type'],
                impact_areas=parsed['impact_areas'],
                reasoning=parsed['reasoning'],
                industry_relevance=parsed.get('industry_relevance', 'direct'),
                industry_category=parsed.get('industry_category', 'retail-marketing')
            )
            
        except Exception as e:
            logger.error(f"Lotte context analysis error: {e}")
            return LotteContextAnalysis(
                article=validation.article,
                impact_type='watchlist',
                impact_areas=['none'],
                reasoning="분석 중 오류 발생"
            )
    
    def _parse_validation_response(self, response: str) -> dict:
        """Parse value validation JSON response."""
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                parsed = json.loads(json_str)
            else:
                parsed = json.loads(response)
            
            # Ensure has_business_value is boolean
            if isinstance(parsed['has_business_value'], str):
                parsed['has_business_value'] = parsed['has_business_value'].lower() in ['true', 'yes', '1']
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing validation response: {e}")
            return {
                'has_business_value': True,
                'reason': 'Parsing error, defaulted to has value'
            }
    
    def _parse_analysis_response(self, response: str) -> dict:
        """Parse Lotte context analysis JSON response."""
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                parsed = json.loads(json_str)
            else:
                parsed = json.loads(response)
            
            # Validate impact_type
            valid_impact_types = ['opportunity', 'threat', 'mixed', 'watchlist']
            if parsed['impact_type'] not in valid_impact_types:
                parsed['impact_type'] = 'watchlist'
            
            # Validate impact_areas
            valid_areas = [
                'membership data usage',
                'targeting / segmentation',
                'advertising agency / data sales business',
                'online–offline linkage',
                'legal / compliance',
                'none'
            ]
            
            if isinstance(parsed['impact_areas'], str):
                parsed['impact_areas'] = [parsed['impact_areas']]
            
            parsed['impact_areas'] = [
                area for area in parsed['impact_areas']
                if area in valid_areas
            ]
            
            if not parsed['impact_areas']:
                parsed['impact_areas'] = ['none']
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing analysis response: {e}")
            return {
                'impact_type': 'watchlist',
                'impact_areas': ['none'],
                'reasoning': '분석 중 오류 발생'
            }
