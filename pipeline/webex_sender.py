"""
Webex message sender for AI News Intelligence Pipeline.
Sends messages to Webex Space using Webex Bot.
"""
import logging
import requests
from typing import List
from datetime import datetime

from .models import WebexMessage

logger = logging.getLogger(__name__)


class WebexSender:
    """Send messages to Webex Space."""
    
    def __init__(self, bot_token: str, room_id: str):
        """
        Initialize Webex sender.
        
        Args:
            bot_token: Webex Bot access token
            room_id: Webex Room/Space ID to send messages to
        """
        self.bot_token = bot_token
        self.room_id = room_id
        self.api_base = "https://webexapis.com/v1"
        self.headers = {
            "Authorization": f"Bearer {bot_token}",
            "Content-Type": "application/json"
        }
    
    def send_messages(
        self, 
        messages: List[WebexMessage],
        analyses: List,
        batch_mode: str = 'single'  # 'single' or 'batch'
    ) -> dict:
        """
        Send messages to Webex Space.
        
        Args:
            messages: List of WebexMessage objects
            analyses: List of LotteContextAnalysis (for industry_relevance)
            batch_mode: 'single' sends each message separately, 
                       'batch' sends all in one message
        
        Returns:
            Dict with send results
        """
        logger.info(f"\n📤 Sending {len(messages)} messages to Webex...")
        logger.info(f"   Mode: {batch_mode}")
        
        if batch_mode == 'single':
            return self._send_individual_messages(messages, analyses)
        else:
            return self._send_batch_message(messages, analyses)
    
    def _send_individual_messages(
        self, 
        messages: List[WebexMessage],
        analyses: List
    ) -> dict:
        """Send each message as a separate Webex message."""
        success_count = 0
        failed_count = 0
        
        for i, (message, analysis) in enumerate(zip(messages, analyses), 1):
            try:
                # Only send direct relevance messages
                if analysis.industry_relevance != 'direct':
                    continue
                
                # Format message text
                text = f"📰 **AI 뉴스 #{i}**\n\n{message.key_summary}\n\n🔗 {message.article_url}"
                
                # Send to Webex
                response = requests.post(
                    f"{self.api_base}/messages",
                    headers=self.headers,
                    json={
                        "roomId": self.room_id,
                        "markdown": text
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    success_count += 1
                    logger.info(f"   ✅ [{i}/{len(messages)}] Sent successfully")
                else:
                    failed_count += 1
                    logger.error(f"   ❌ [{i}/{len(messages)}] Failed: {response.status_code} - {response.text}")
                
            except Exception as e:
                failed_count += 1
                logger.error(f"   ❌ [{i}/{len(messages)}] Error: {e}")
        
        logger.info(f"\n✅ Webex send complete: {success_count} succeeded, {failed_count} failed")
        
        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "total": len(messages)
        }
    
    def _send_batch_message(
        self, 
        messages: List[WebexMessage],
        analyses: List
    ) -> dict:
        """Send all messages as one batch Webex message."""
        try:
            # Separate direct and indirect
            direct_messages = []
            
            for message, analysis in zip(messages, analyses):
                if analysis.industry_relevance == 'direct':
                    direct_messages.append(message)
            
            # Build batch message
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            batch_text = f"""# 🔥 AI 뉴스 인텔리전스 ({timestamp})
롯데멤버스 직접 연관 뉴스 - {len(direct_messages)}건

---

"""
            
            for i, message in enumerate(direct_messages, 1):
                batch_text += f"""## 📰 뉴스 #{i}

{message.key_summary}

🔗 [기사 원문]({message.article_url})

---

"""
            
            # Send to Webex
            response = requests.post(
                f"{self.api_base}/messages",
                headers=self.headers,
                json={
                    "roomId": self.room_id,
                    "markdown": batch_text
                },
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Batch message sent successfully ({len(direct_messages)} articles)")
                return {
                    "success_count": len(direct_messages),
                    "failed_count": 0,
                    "total": len(direct_messages)
                }
            else:
                logger.error(f"❌ Batch send failed: {response.status_code} - {response.text}")
                return {
                    "success_count": 0,
                    "failed_count": len(direct_messages),
                    "total": len(direct_messages)
                }
        
        except Exception as e:
            logger.error(f"❌ Batch send error: {e}")
            return {
                "success_count": 0,
                "failed_count": len(messages),
                "total": len(messages)
            }
    
    def send_test_message(self) -> bool:
        """Send a test message to verify connection."""
        try:
            test_text = f"""# 🧪 AI 뉴스 파이프라인 테스트

테스트 시각: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

✅ Webex 연동이 정상적으로 작동합니다!
"""
            
            response = requests.post(
                f"{self.api_base}/messages",
                headers=self.headers,
                json={
                    "roomId": self.room_id,
                    "markdown": test_text
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✅ Test message sent successfully")
                return True
            else:
                logger.error(f"❌ Test message failed: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Test message error: {e}")
            return False
