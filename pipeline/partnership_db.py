"""
STEP 7: Partnership database generation from analyzed articles.
"""
import logging
import json
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI

from .models import LotteContextAnalysis
from .config import PipelineConfig, RateLimiter

logger = logging.getLogger(__name__)


@dataclass
class CompanyInfo:
    """Information about a potential partnership company."""
    name: str
    category: str  # solution, case, technology, regulation
    field: str  # AI 검색, 광고 플랫폼, etc.
    recent_achievement: str
    collaboration_point: str
    article_url: str


class PartnershipDatabaseGenerator:
    """Extract company information and generate partnership database."""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=PipelineConfig.LLM_MODEL,
            temperature=0.1
        )
        self.rate_limiter = RateLimiter(PipelineConfig.LLM_REQUESTS_PER_MINUTE)
    
    def generate_database(
        self, 
        analyses: List[LotteContextAnalysis]
    ) -> List[CompanyInfo]:
        """
        Extract company information from articles and generate database.
        
        Args:
            analyses: Articles with Lotte context analysis
            
        Returns:
            List of CompanyInfo objects
        """
        logger.info("\n" + "=" * 60)
        logger.info("STEP 7: PARTNERSHIP DATABASE GENERATION")
        logger.info("=" * 60)
        
        # Only process direct relevance articles
        direct_analyses = [a for a in analyses if a.industry_relevance == 'direct']
        logger.info(f"Processing {len(direct_analyses)} direct relevance articles...")
        
        all_companies = []
        
        for i, analysis in enumerate(direct_analyses, 1):
            logger.info(f"\n[{i}/{len(direct_analyses)}] Extracting from: {analysis.article.title[:50]}...")
            
            try:
                self.rate_limiter.wait_if_needed()
                companies = self._extract_companies(analysis)
                
                if companies:
                    all_companies.extend(companies)
                    logger.info(f"   ✅ Extracted {len(companies)} companies")
                else:
                    logger.info(f"   ℹ️  No companies extracted")
                    
            except Exception as e:
                logger.error(f"   ⚠️  Extraction error: {e}")
        
        # Remove duplicates
        logger.info(f"\n🔍 Deduplicating companies...")
        unique_companies = self._deduplicate_companies(all_companies)
        
        logger.info(f"✅ Partnership database complete:")
        logger.info(f"   Total companies: {len(unique_companies)}")
        logger.info(f"   By category:")
        
        by_category = {}
        for company in unique_companies:
            by_category[company.category] = by_category.get(company.category, 0) + 1
        
        for cat, count in sorted(by_category.items()):
            logger.info(f"      {cat}: {count}")
        
        return unique_companies
    
    def _extract_companies(
        self, 
        analysis: LotteContextAnalysis
    ) -> List[CompanyInfo]:
        """Extract company information from a single article."""
        
        # Determine category from impact areas and reasoning
        # Default to technology
        category = 'technology'
        
        # Use simple heuristics based on content
        content_lower = f"{analysis.article.title} {analysis.reasoning}".lower()
        
        if any(word in content_lower for word in ['광고', '마케팅', '솔루션', '플랫폼', 'crm']):
            category = 'solution'
        elif any(word in content_lower for word in ['도입', '사례', '활용', '적용', '구현']):
            category = 'case'
        elif 'legal / compliance' in analysis.impact_areas or any(word in content_lower for word in ['규제', '법률', '법안', '컴플라이언스']):
            category = 'regulation'
        
        prompt = f"""You are extracting company information from an AI news article for a partnership database.

**Article:**
Title: {analysis.article.title}
Content: {analysis.article.full_content[:2000]}...

**Lotte Members Context:**
Impact: {analysis.impact_type}
Reasoning: {analysis.reasoning}

**Task:**
Extract ALL companies/organizations mentioned in this article that could be potential partners.

For EACH company, provide:
1. **name**: Company or organization name (Korean preferred)
2. **field**: Specific AI field/technology (e.g., "AI 검색", "광고 플랫폼", "고객 분석")
3. **recent_achievement**: What they achieved/announced in THIS article (1 sentence)
4. **collaboration_point**: How Lotte Members could collaborate with them (1 sentence, specific)

**Output Format (JSON array):**
[
  {{
    "name": "네이버",
    "field": "AI 검색, 개인화 추천",
    "recent_achievement": "GPT-4 기반 하이퍼클로바X 출시, 검색 정확도 40% 향상",
    "collaboration_point": "롯데멤버스 구매 데이터로 개인화 검색 엔진 구축 가능"
  }},
  ...
]

**Important:**
- Extract ONLY companies that are actively doing something in AI
- Skip generic mentions ("국내 기업들", "업계" etc.)
- Be specific about field and achievements
- Collaboration point must be actionable for Lotte Members

Respond ONLY with valid JSON array, no additional text."""
        
        try:
            response = self.llm.invoke(prompt).content
            parsed = self._parse_companies_response(response)
            
            companies = []
            for item in parsed:
                companies.append(CompanyInfo(
                    name=item['name'],
                    category=category,
                    field=item['field'],
                    recent_achievement=item['recent_achievement'],
                    collaboration_point=item['collaboration_point'],
                    article_url=analysis.article.url
                ))
            
            return companies
            
        except Exception as e:
            logger.error(f"Company extraction error: {e}")
            return []
    
    def _parse_companies_response(self, response: str) -> List[Dict]:
        """Parse LLM JSON array response."""
        try:
            # Extract JSON array
            start = response.find('[')
            end = response.rfind(']') + 1
            
            if start != -1 and end > start:
                json_str = response[start:end]
                parsed = json.loads(json_str)
            else:
                parsed = json.loads(response)
            
            # Validate each item
            validated = []
            for item in parsed:
                if all(key in item for key in ['name', 'field', 'recent_achievement', 'collaboration_point']):
                    validated.append(item)
            
            return validated
            
        except Exception as e:
            logger.error(f"Error parsing companies response: {e}")
            return []
    
    def _deduplicate_companies(
        self, 
        companies: List[CompanyInfo]
    ) -> List[CompanyInfo]:
        """Remove duplicate companies, keeping the most informative entry."""
        
        # Group by company name (case-insensitive)
        by_name = {}
        for company in companies:
            name_key = company.name.lower().strip()
            
            if name_key not in by_name:
                by_name[name_key] = []
            
            by_name[name_key].append(company)
        
        # Keep one per company (prefer longer achievement descriptions)
        unique = []
        for name_key, company_list in by_name.items():
            # Sort by achievement length (more detailed = better)
            best = max(company_list, key=lambda c: len(c.recent_achievement))
            unique.append(best)
        
        return unique
    
    def save_to_markdown(
        self, 
        companies: List[CompanyInfo], 
        filename: str = "collaboration_partners.md"
    ):
        """
        Save partnership database to Markdown file with tables grouped by field.
        
        Args:
            companies: List of CompanyInfo objects
            filename: Output filename
        """
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y-%m-%d")
        
        # Group by field (AI 광고, 개인화 추천, etc.)
        by_field = {}
        
        for company in companies:
            # Normalize field names (remove extra spaces, commas)
            fields = [f.strip() for f in company.field.split(',')]
            
            # Use primary field (first one)
            primary_field = fields[0] if fields else 'AI 기술'
            
            if primary_field not in by_field:
                by_field[primary_field] = []
            
            by_field[primary_field].append(company)
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # Header
                f.write("# AI 협업 가능 업체 리스트\n\n")
                f.write(f"**업데이트**: {timestamp}\n")
                f.write(f"**총 업체 수**: {len(companies)}개\n\n")
                f.write("---\n\n")
                
                # Field-based tables (grouped by actual business fields)
                field_emoji = {
                    'AI 광고': '🎯',
                    '개인화 추천': '🔍',
                    'AI 마케팅': '📢',
                    '데이터 분석': '📊',
                    '고객 인사이트': '💡',
                    '챗봇': '🤖',
                    'LLM': '🧠',
                    '검색': '🔎',
                    '음성인식': '🎤',
                    '이미지 생성': '🎨'
                }
                
                # Sort fields by number of companies (descending)
                sorted_fields = sorted(by_field.items(), key=lambda x: len(x[1]), reverse=True)
                
                for field_name, companies_in_field in sorted_fields:
                    emoji = field_emoji.get(field_name, '💼')
                    
                    f.write(f"## {emoji} {field_name} ({len(companies_in_field)}개 업체)\n\n")
                    
                    # Table
                    f.write("| 회사명 | 최근 성과 | 협업 포인트 | 기사 출처 |\n")
                    f.write("|--------|-----------|-------------|----------|\n")
                    
                    for company in companies_in_field:
                        # Truncate long text for table readability
                        achievement = company.recent_achievement[:100] + "..." if len(company.recent_achievement) > 100 else company.recent_achievement
                        collab = company.collaboration_point[:100] + "..." if len(company.collaboration_point) > 100 else company.collaboration_point
                        
                        # Escape pipe characters in content
                        name = company.name.replace('|', '\\|')
                        achievement = achievement.replace('|', '\\|')
                        collab = collab.replace('|', '\\|')
                        
                        f.write(f"| {name} | {achievement} | {collab} | [링크]({company.article_url}) |\n")
                    
                    f.write("\n---\n\n")
                
                # Footer
                f.write("## 📌 활용 가이드\n\n")
                f.write("분야별로 롯데멤버스와 협업 가능한 AI 기업들을 정리했습니다.\n\n")
                f.write("- **최근 성과**: 해당 기업의 최신 AI 활용 사례 및 기술 성과\n")
                f.write("- **협업 포인트**: 롯데멤버스와의 구체적인 협업 가능성 및 시너지\n\n")
                f.write("---\n\n")
                f.write(f"*Generated by AI News Intelligence Pipeline - {timestamp}*\n")
            
            logger.info(f"\n💾 Partnership database saved: {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save partnership database: {e}")
