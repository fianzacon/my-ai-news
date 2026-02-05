"""
STEP 6: Webex message output generation with strict format.
"""
import logging
import json
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI

from .models import LotteContextAnalysis, WebexMessage
from .config import PipelineConfig

logger = logging.getLogger(__name__)


class WebexFormatter:
    """Generate Webex-ready messages with strict formatting."""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=PipelineConfig.LLM_MODEL,
            temperature=0.2  # Slightly higher for more natural language
        )
    
    def generate_messages(
        self, 
        analyses: List[LotteContextAnalysis]
    ) -> List[WebexMessage]:
        """
        Generate Webex messages for all analyzed articles.
        
        Args:
            analyses: Articles with Lotte context analysis
            
        Returns:
            List of WebexMessage objects
        """
        logger.info("\n" + "=" * 60)
        logger.info("STEP 6: WEBEX MESSAGE OUTPUT TEMPLATE (STRICT FORMAT)")
        logger.info("=" * 60)
        
        # Separate articles by industry relevance
        direct_analyses = [a for a in analyses if a.industry_relevance == 'direct']
        indirect_analyses = [a for a in analyses if a.industry_relevance == 'indirect']
        
        logger.info(f"\n📊 Article distribution:")
        logger.info(f"   Direct relevance (HIGH PRIORITY): {len(direct_analyses)}")
        logger.info(f"   Indirect relevance (REFERENCE): {len(indirect_analyses)}")
        
        messages = []
        
        # Generate detailed messages for direct relevance
        logger.info("\n🔥 Generating HIGH PRIORITY messages (detailed)...")
        for i, analysis in enumerate(direct_analyses, 1):
            logger.info(f"   [{i}/{len(direct_analyses)}] {analysis.article.title[:50]}...")
            
            try:
                message = self._generate_single_message(analysis)
                messages.append(message)
            except Exception as e:
                logger.error(f"   ⚠️  Error: {e}")
                message = self._create_fallback_message(analysis)
                messages.append(message)
        
        # Generate brief messages for indirect relevance
        logger.info("\n📋 Generating REFERENCE messages (brief)...")
        for i, analysis in enumerate(indirect_analyses, 1):
            logger.info(f"   [{i}/{len(indirect_analyses)}] {analysis.article.title[:50]}...")
            
            try:
                message = self._generate_brief_message(analysis)
                messages.append(message)
            except Exception as e:
                logger.error(f"   ⚠️  Error: {e}")
                message = self._create_fallback_message(analysis)
                messages.append(message)
        
        logger.info(f"\n✅ Webex message generation complete: {len(messages)} messages")
        
        return messages
    
    def _generate_single_message(
        self, 
        analysis: LotteContextAnalysis
    ) -> WebexMessage:
        """
        Generate a single Webex message with strict format.
        
        Args:
            analysis: Article with Lotte context
            
        Returns:
            WebexMessage object
        """
        prompt = self._build_message_prompt(analysis)
        
        try:
            response = self.llm.invoke(prompt).content
            parsed = self._parse_message_response(response)
            
            return WebexMessage(
                article_url=analysis.article.url,
                company_entity=parsed['company_entity'],
                key_summary=parsed['key_summary'],
                action=parsed['action']
            )
            
        except Exception as e:
            logger.error(f"Message generation error: {e}")
            return self._create_fallback_message(analysis)
    
    def _generate_brief_message(
        self, 
        analysis: LotteContextAnalysis
    ) -> WebexMessage:
        """
        Generate a brief one-line message for indirect relevance articles.
        
        Args:
            analysis: Article with Lotte context
            
        Returns:
            WebexMessage with brief format
        """
        # For indirect articles, create simple one-liner
        category_emoji = {
            'healthcare': '🏥',
            'manufacturing': '🏭',
            'robotics': '🤖',
            'energy': '⚡',
            'general-ai': '🧠',
            'other': '📌'
        }
        
        emoji = category_emoji.get(analysis.industry_category, '📌')
        category_name = {
            'healthcare': 'Healthcare',
            'manufacturing': 'Manufacturing',
            'robotics': 'Robotics',
            'energy': 'Energy',
            'general-ai': 'General AI',
            'other': 'Other'
        }.get(analysis.industry_category, 'Other')
        
        # Create brief summary (just title + one-line context)
        brief_summary = f"[{category_name}] {analysis.article.title}"
        
        return WebexMessage(
            article_url=analysis.article.url,
            company_entity=category_name,
            key_summary=brief_summary,
            action="참고용 (업종 비연관)"
        )
    
    def _build_message_prompt(self, analysis: LotteContextAnalysis) -> str:
        """Build the prompt for Webex message generation."""
        
        prompt = f"""You are creating a Webex notification for Lotte Members marketing/advertising practitioners.

**Article Information:**
Title: {analysis.article.title}
Content: {analysis.article.full_content[:2500]}...
Impact Type: {analysis.impact_type}
Impact Areas: {', '.join(analysis.impact_areas)}
Reasoning: {analysis.reasoning}

**Task:**
Write a 3-4 line summary following this NEW structure:

**Line 1-2: 기사의 핵심 팩트**
- 무슨 일이 일어났는지 명확히 전달
- 주어와 동사를 명확히 쓰고, 사실 중심으로 작성

**Line 3: 롯데멤버스 인사이트 (선택적)**
- 롯데멤버스와 연관성이 **명확하고 구체적인 경우에만** 추가
- 괄호 안에 한 줄로 간결하게: (→ 구체적 행동/시사점)
- 억지로 연결하지 말 것. 연관성이 약하면 팩트만 전달.

**Output Format (JSON):**
{{
  "key_summary": "3-4 line summary in Korean (팩트 중심 + 선택적 인사이트)"
}}

**CRITICAL RULES:**
- 팩트를 먼저, 인사이트는 명확한 경우에만
- 억지 연결 금지 (예: 수산물 데이터 → 롯데 타겟팅 활용)
- 3-4 lines maximum (250 characters)
- Korean language
- 구체적이고 실행 가능한 내용만

Respond ONLY with valid JSON, no additional text."""
        
        return prompt
    
    def _parse_message_response(self, response: str) -> dict:
        """Parse LLM JSON response for Webex message."""
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                parsed = json.loads(json_str)
            else:
                parsed = json.loads(response)
            
            # Validate required fields
            if 'key_summary' not in parsed or not parsed['key_summary']:
                raise ValueError("Missing or empty field: key_summary")
            
            # Truncate if too long
            parsed['key_summary'] = parsed['key_summary'][:600]  # Safety limit
            
            # Add legacy fields for compatibility
            parsed['company_entity'] = ""
            parsed['action'] = ""
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing message response: {e}")
            logger.error(f"Response was: {response}")
            raise
    
    def _create_fallback_message(
        self, 
        analysis: LotteContextAnalysis
    ) -> WebexMessage:
        """
        Create a fallback message if LLM generation fails.
        
        Args:
            analysis: Article with Lotte context
            
        Returns:
            WebexMessage with basic content
        """
        # Extract potential company names (very basic)
        title = analysis.article.title
        company = "관련 기업"
        
        # Try to extract from title
        for keyword in ['구글', 'Google', '네이버', 'Naver', 'OpenAI', '삼성', 'Samsung', 
                       'LG', '카카오', 'Kakao', '롯데', 'Lotte']:
            if keyword in title:
                company = keyword
                break
        
        # Create basic summary from title and reasoning
        summary = f"{analysis.article.title[:100]}... {analysis.reasoning}"
        if len(summary) > 300:
            summary = summary[:297] + "..."
        
        # Create basic action based on impact type
        action_map = {
            'opportunity': "신규 기회 검토 필요",
            'threat': "경쟁 대응 전략 수립 필요",
            'mixed': "영향 분석 및 대응 방안 검토 필요",
            'watchlist': "동향 모니터링 필요"
        }
        action = action_map.get(analysis.impact_type, "관련 팀과 협의 필요")
        
        return WebexMessage(
            article_url=analysis.article.url,
            key_summary=summary
        )
    
    def save_messages_to_file(
        self, 
        analyses: List[LotteContextAnalysis],
        messages: List[WebexMessage], 
        filename_prefix: str = "webex_messages"
    ):
        """
        Save messages to TWO separate files: HIGH_PRIORITY and REFERENCE.
        
        Args:
            analyses: Original analyses (to get industry_relevance)
            messages: List of WebexMessage objects
            filename_prefix: Prefix for output filenames
        """
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Map messages to analyses
        direct_messages = []
        indirect_messages = []
        
        for analysis, message in zip(analyses, messages):
            if analysis.industry_relevance == 'direct':
                direct_messages.append((analysis, message))
            else:
                indirect_messages.append((analysis, message))
        
        # Save HIGH_PRIORITY file (detailed)
        high_priority_file = f"{filename_prefix}_HIGH_PRIORITY_{timestamp}.txt"
        self._save_high_priority_file(direct_messages, high_priority_file)
        
        # Save REFERENCE file (brief)
        reference_file = f"{filename_prefix}_REFERENCE_{timestamp}.txt"
        self._save_reference_file(indirect_messages, reference_file)
    
    def _save_high_priority_file(
        self, 
        messages: List[tuple], 
        filename: str
    ):
        """Save detailed high-priority messages."""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("🔥 HIGH PRIORITY - AI NEWS INTELLIGENCE\n")
                f.write("롯데멤버스 직접 연관 뉴스 (상세)\n")
                f.write("=" * 60 + "\n\n")
                
                for i, (analysis, message) in enumerate(messages, 1):
                    f.write(f"{'='*60}\n")
                    f.write(f"MESSAGE {i}/{len(messages)}\n")
                    f.write(f"{'='*60}\n")
                    f.write(message.format())
                    f.write("\n\n")
            
            logger.info(f"💾 HIGH PRIORITY messages saved: {filename} ({len(messages)} articles)")
            
        except Exception as e:
            logger.error(f"Failed to save HIGH PRIORITY file: {e}")
    
    def _save_reference_file(
        self, 
        messages: List[tuple], 
        filename: str
    ):
        """Save brief reference messages grouped by category."""
        try:
            # Group by category
            by_category = {}
            for analysis, message in messages:
                category = analysis.industry_category or 'other'
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append((analysis, message))
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("📋 REFERENCE - AI NEWS INTELLIGENCE\n")
                f.write("간접 연관 뉴스 (참고용 - 한 줄 요약)\n")
                f.write("=" * 60 + "\n\n")
                
                category_names = {
                    'healthcare': '🏥 Healthcare (의료/헬스케어)',
                    'manufacturing': '🏭 Manufacturing (제조/생산)',
                    'robotics': '🤖 Robotics (로봇/자율주행)',
                    'energy': '⚡ Energy (에너지/전력)',
                    'general-ai': '🧠 General AI (범용 AI 기술)',
                    'other': '📌 Other (기타)'
                }
                
                for category in ['healthcare', 'manufacturing', 'robotics', 'energy', 'general-ai', 'other']:
                    if category in by_category:
                        items = by_category[category]
                        f.write(f"\n{category_names.get(category, category)}\n")
                        f.write("-" * 60 + "\n")
                        
                        for analysis, message in items:
                            f.write(f"• {analysis.article.title}\n")
                            f.write(f"  {analysis.reasoning}\n")
                            f.write(f"  🔗 {analysis.article.url}\n\n")
            
            logger.info(f"💾 REFERENCE messages saved: {filename} ({len(messages)} articles)")
            
        except Exception as e:
            logger.error(f"Failed to save REFERENCE file: {e}")
