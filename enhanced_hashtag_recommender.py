import streamlit as st
import requests
import json
import re
import sqlite3
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict

# Page configuration
st.set_page_config(
    page_title="AI Hashtag Optimizer Pro",
    page_icon="🚀",
    layout="wide"
)

# Styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 1rem;
        background: linear-gradient(120deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

class PerformanceDatabase:
    """SQLite database for storing post performance data"""
    
    def __init__(self, db_path: str = "hashtag_performance.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                content_length INTEGER,
                has_question INTEGER,
                has_emoji INTEGER,
                predicted_score INTEGER
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hashtags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER,
                hashtag TEXT NOT NULL,
                predicted_relevance INTEGER,
                FOREIGN KEY (post_id) REFERENCES posts(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER UNIQUE,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                impressions INTEGER DEFAULT 0,
                engagement_rate REAL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hashtag_stats (
                hashtag TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                total_uses INTEGER DEFAULT 0,
                avg_engagement REAL DEFAULT 0,
                success_rate REAL DEFAULT 0,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_prediction(self, platform: str, content: str, hashtags: List[Dict], 
                       predicted_score: int) -> int:
        """Save a prediction for future tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO posts (platform, content, content_length, has_question, 
                             has_emoji, predicted_score)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            platform,
            content,
            len(content),
            1 if '?' in content else 0,
            1 if any(emoji in content for emoji in '😊🔥💯❤️👍🎉✨💪🙌') else 0,
            predicted_score
        ))
        
        post_id = cursor.lastrowid
        
        for tag in hashtags:
            cursor.execute("""
                INSERT INTO hashtags (post_id, hashtag, predicted_relevance)
                VALUES (?, ?, ?)
            """, (post_id, tag['tag'], tag['relevance']))
        
        conn.commit()
        conn.close()
        
        return post_id
    
    def update_actual_performance(self, post_id: int, likes: int, comments: int, 
                                 shares: int, impressions: int):
        """Update with actual performance metrics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        engagement_rate = 0
        if impressions > 0:
            engagement_rate = ((likes + comments + shares) / impressions) * 100
        
        cursor.execute("""
            INSERT OR REPLACE INTO performance 
            (post_id, likes, comments, shares, impressions, engagement_rate, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (post_id, likes, comments, shares, impressions, engagement_rate))
        
        cursor.execute("SELECT hashtag FROM hashtags WHERE post_id = ?", (post_id,))
        hashtags = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT platform FROM posts WHERE id = ?", (post_id,))
        platform = cursor.fetchone()[0]
        
        for hashtag in hashtags:
            cursor.execute("""
                INSERT INTO hashtag_stats (hashtag, platform, total_uses, avg_engagement, last_used)
                VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(hashtag) DO UPDATE SET
                    total_uses = total_uses + 1,
                    avg_engagement = (avg_engagement * (total_uses - 1) + ?) / total_uses,
                    last_used = CURRENT_TIMESTAMP
            """, (hashtag, platform, engagement_rate, engagement_rate))
        
        conn.commit()
        conn.close()
    
    def get_top_hashtags(self, platform: str, limit: int = 20) -> List[Dict]:
        """Get historically successful hashtags"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT hashtag, total_uses, avg_engagement, success_rate
            FROM hashtag_stats
            WHERE platform = ? AND total_uses >= 2
            ORDER BY avg_engagement DESC
            LIMIT ?
        """, (platform, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'hashtag': row[0],
                'total_uses': row[1],
                'avg_engagement': row[2],
                'success_rate': row[3]
            })
        
        conn.close()
        return results
    
    def get_similar_successful_posts(self, content: str, platform: str, 
                                     limit: int = 5) -> List[Dict]:
        """Find similar posts that performed well"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        keywords = set(re.findall(r'\b[a-zA-Z]{4,}\b', content.lower()))
        
        cursor.execute("""
            SELECT p.id, p.content, perf.engagement_rate, 
                   GROUP_CONCAT(h.hashtag, ', ') as hashtags
            FROM posts p
            JOIN performance perf ON p.id = perf.post_id
            JOIN hashtags h ON p.id = h.post_id
            WHERE p.platform = ? AND perf.engagement_rate > 3.0
            GROUP BY p.id
            ORDER BY perf.engagement_rate DESC
            LIMIT ?
        """, (platform, limit * 2))
        
        results = []
        for row in cursor.fetchall():
            post_keywords = set(re.findall(r'\b[a-zA-Z]{4,}\b', row[1].lower()))
            similarity = len(keywords & post_keywords) / len(keywords | post_keywords) if keywords | post_keywords else 0
            
            if similarity > 0.2:
                results.append({
                    'post_id': row[0],
                    'content': row[1][:100] + '...' if len(row[1]) > 100 else row[1],
                    'engagement_rate': row[2],
                    'hashtags': row[3],
                    'similarity': similarity
                })
        
        conn.close()
        return sorted(results, key=lambda x: x['engagement_rate'], reverse=True)[:limit]
    
    def get_learning_insights(self, platform: str) -> Dict:
        """Get insights from historical data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        insights = {}
        
        cursor.execute("SELECT COUNT(*) FROM posts WHERE platform = ?", (platform,))
        insights['total_posts'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM posts p
            JOIN performance perf ON p.id = perf.post_id
            WHERE p.platform = ?
        """, (platform,))
        insights['tracked_posts'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT AVG(engagement_rate) FROM performance perf
            JOIN posts p ON p.id = perf.post_id
            WHERE p.platform = ?
        """, (platform,))
        result = cursor.fetchone()[0]
        insights['avg_engagement'] = result if result else 0
        
        cursor.execute("""
            SELECT hashtag, avg_engagement FROM hashtag_stats
            WHERE platform = ? AND total_uses >= 3
            ORDER BY avg_engagement DESC
            LIMIT 1
        """, (platform,))
        result = cursor.fetchone()
        if result:
            insights['best_hashtag'] = {'tag': result[0], 'engagement': result[1]}
        
        cursor.execute("""
            SELECT AVG(p.content_length) FROM posts p
            JOIN performance perf ON p.id = perf.post_id
            WHERE p.platform = ? AND perf.engagement_rate > 
                (SELECT AVG(engagement_rate) FROM performance)
        """, (platform,))
        result = cursor.fetchone()[0]
        insights['optimal_length'] = int(result) if result else None
        
        conn.close()
        return insights

class OllamaAPI:
    """Handler for Ollama API interactions"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.model = "llama3.2:3b"
    
    def is_available(self) -> bool:
        """Check if Ollama is running"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate response from Ollama"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()['response']
            else:
                return None
        except Exception as e:
            st.error(f"Error generating response: {str(e)}")
            return None

class EnhancedHashtagAnalyzer:
    """Enhanced analyzer with learning capabilities"""
    
    def __init__(self, ollama: OllamaAPI, db: PerformanceDatabase):
        self.ollama = ollama
        self.db = db
    
    def analyze_content(self, text: str, platform: str) -> Dict:
        """Analyze content with learning from historical data"""
        
        top_hashtags = self.db.get_top_hashtags(platform, limit=15)
        similar_posts = self.db.get_similar_successful_posts(text, platform)
        learning_insights = self.db.get_learning_insights(platform)
        
        hashtags = self._generate_hashtags_with_learning(
            text, platform, top_hashtags, similar_posts
        )
        
        performance_score = self._score_with_learning(
            text, hashtags, platform, learning_insights
        )
        
        insights = self._generate_insights_with_learning(
            text, platform, performance_score, learning_insights
        )
        
        post_id = self.db.save_prediction(
            platform, text, hashtags, performance_score['engagement_potential']
        )
        
        print(f"DEBUG: Final hashtag count before returning: {len(hashtags)}")
        print(f"DEBUG: Hashtags: {[h['tag'] for h in hashtags]}")
        
        return {
            'hashtags': hashtags,
            'performance_score': performance_score,
            'insights': insights,
            'post_id': post_id,
            'similar_posts': similar_posts,
            'learning_insights': learning_insights
        }
    
    def _generate_hashtags_with_learning(self, text: str, platform: str,
                                        top_hashtags: List[Dict],
                                        similar_posts: List[Dict]) -> List[Dict]:
        """Generate hashtags using learned patterns"""
        
        learned_context = ""
        if top_hashtags:
            top_tags = [f"#{t['hashtag']} (avg engagement: {t['avg_engagement']:.1f}%)" 
                       for t in top_hashtags[:5]]
            learned_context += f"\n\nTOP PERFORMING HASHTAGS:\n" + "\n".join(top_tags)
        
        if similar_posts:
            learned_context += f"\n\nSIMILAR SUCCESSFUL POSTS:\n"
            for post in similar_posts[:3]:
                learned_context += f"- '{post['content']}' ({post['engagement_rate']:.1f}%) used: {post['hashtags']}\n"
        
        platform_context = {
            'Twitter': 'Twitter posts perform best with 1-3 highly relevant hashtags.',
            'Instagram': 'Instagram posts can use 8-15 hashtags effectively.'
        }
        
        num_hashtags = 3 if platform == 'Twitter' else 12
        
        system_prompt = f"""You are a social media expert specializing in {platform}.
{platform_context[platform]}

You have REAL PERFORMANCE DATA from previous posts. Use this to inform recommendations.{learned_context}

Prioritize hashtags that have historically performed well."""

        if platform == 'Twitter':
            prompt = f"""Analyze this Twitter post and suggest hashtags:

Post: "{text}"

YOU MUST PROVIDE EXACTLY 3 HASHTAGS. NO MORE, NO LESS.

Return ONLY this JSON array with 3 entries:
[
  {{"tag": "hashtag1", "relevance": 95, "popularity": "High", "reason": "why this works"}},
  {{"tag": "hashtag2", "relevance": 90, "popularity": "Medium", "reason": "why this works"}},
  {{"tag": "hashtag3", "relevance": 85, "popularity": "Medium", "reason": "why this works"}}
]

Return ONLY the JSON array. Nothing else."""
        else:
            prompt = f"""Analyze this Instagram post and suggest hashtags:

Post: "{text}"

Provide EXACTLY {num_hashtags} hashtags. Format as JSON array:
[
  {{"tag": "example", "relevance": 95, "popularity": "High", "reason": "explanation"}},
  {{"tag": "sample", "relevance": 90, "popularity": "Medium", "reason": "explanation"}}
]

IMPORTANT: Return ONLY the JSON array with exactly {num_hashtags} hashtags, nothing else."""

        response = self.ollama.generate(prompt, system_prompt)
        
        if response:
            try:
                # Clean up response - remove any markdown code blocks
                cleaned_response = response.strip()
                if cleaned_response.startswith('```'):
                    # Remove markdown code blocks
                    cleaned_response = re.sub(r'```json\s*|\s*```', '', cleaned_response).strip()
                
                # Try to extract JSON array from response
                json_match = re.search(r'\[\s*\{.*?\}\s*\]', cleaned_response, re.DOTALL)
                if json_match:
                    hashtags = json.loads(json_match.group())
                    
                    print(f"DEBUG: LLM returned {len(hashtags)} hashtags for {platform}")
                    
                    # Ensure we have the right number
                    if len(hashtags) < num_hashtags:
                        print(f"DEBUG: Not enough hashtags from LLM, using fallback")
                        return self._fallback_hashtags(text, platform, top_hashtags)
                    
                    # Boost relevance for historically successful hashtags
                    for tag in hashtags:
                        for top_tag in top_hashtags:
                            if tag['tag'].lower() == top_tag['hashtag'].lower():
                                tag['relevance'] = min(100, tag['relevance'] + 10)
                                tag['reason'] += f" [✓ Data: {top_tag['avg_engagement']:.1f}% avg]"
                    
                    result = hashtags[:num_hashtags]
                    print(f"DEBUG: Returning {len(result)} hashtags")
                    return result
                else:
                    print(f"DEBUG: Could not extract JSON from LLM response")
            except Exception as e:
                print(f"DEBUG: Error parsing LLM response: {e}")
                print(f"DEBUG: Response was: {response[:200]}")
        
        print(f"DEBUG: Using fallback for {platform}")
        return self._fallback_hashtags(text, platform, top_hashtags)
    
    def _fallback_hashtags(self, text: str, platform: str, 
                          top_hashtags: List[Dict]) -> List[Dict]:
        """Fallback with learned hashtags"""
        # Extract keywords from text
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())  # Changed from 4+ to 3+ chars
        common_words = {'this', 'that', 'with', 'from', 'have', 'been', 'were', 'their', 
                       'would', 'about', 'when', 'just', 'like', 'some', 'what', 'your',
                       'will', 'they', 'them', 'into', 'than', 'more', 'very', 'can'}
        keywords = [w for w in words if w not in common_words]
        
        hashtags = []
        target_count = 3 if platform == 'Twitter' else 12
        
        # Strategy 1: Add keyword-based hashtags
        for i, word in enumerate(keywords[:target_count]):
            if len(hashtags) >= target_count:
                break
            hashtags.append({
                'tag': word,
                'relevance': 85 - (i * 5),
                'popularity': 'Medium',
                'reason': 'Extracted from content keywords'
            })
        
        # Strategy 2: Fill with proven hashtags if we have data
        if len(hashtags) < target_count and top_hashtags:
            for tag in top_hashtags:
                if len(hashtags) >= target_count:
                    break
                # Avoid duplicates
                if not any(h['tag'].lower() == tag['hashtag'].lower() for h in hashtags):
                    hashtags.append({
                        'tag': tag['hashtag'],
                        'relevance': 90,
                        'popularity': 'High',
                        'reason': f"Proven performer: {tag['avg_engagement']:.1f}% avg"
                    })
        
        # Strategy 3: Generic fallback hashtags if still not enough
        if len(hashtags) < target_count:
            generic_tags = ['content', 'socialmedia', 'marketing', 'community', 'growth', 
                          'tips', 'inspiration', 'motivation', 'business', 'success', 
                          'trending', 'viral', 'engage', 'share', 'follow']
            
            for generic_tag in generic_tags:
                if len(hashtags) >= target_count:
                    break
                # Avoid duplicates
                if not any(h['tag'].lower() == generic_tag for h in hashtags):
                    hashtags.append({
                        'tag': generic_tag,
                        'relevance': 70,
                        'popularity': 'Medium',
                        'reason': 'General engagement hashtag'
                    })
        
        # Final safety check: ensure exact count
        return hashtags[:target_count]
    
    def _score_with_learning(self, text: str, hashtags: List[Dict], 
                            platform: str, insights: Dict) -> Dict:
        """Score using learned patterns"""
        
        scores = {
            'content_quality': self._score_content_quality_learned(text, platform, insights),
            'hashtag_strategy': self._score_hashtag_strategy(hashtags, platform),
            'timing_relevance': self._score_timing(text),
            'data_confidence': self._calculate_data_confidence(insights)
        }
        
        scores['engagement_potential'] = int(
            scores['content_quality'] * 0.35 +
            scores['hashtag_strategy'] * 0.35 +
            scores['timing_relevance'] * 0.20 +
            scores['data_confidence'] * 0.10
        )
        
        return scores
    
    def _score_content_quality_learned(self, text: str, platform: str, 
                                      insights: Dict) -> int:
        """Score content using learned optimal patterns"""
        score = 50
        text_length = len(text)
        
        if insights.get('optimal_length'):
            optimal = insights['optimal_length']
            length_diff = abs(text_length - optimal)
            if length_diff < 50:
                score += 25
            elif length_diff < 100:
                score += 15
            else:
                score += 5
        else:
            if platform == 'Twitter' and 100 <= text_length <= 280:
                score += 20
            elif platform == 'Instagram' and 138 <= text_length <= 2200:
                score += 20
        
        if '?' in text:
            score += 10
        if any(emoji in text for emoji in '😊🔥💯❤️👍🎉✨💪🙌'):
            score += 10
        if text[0].isupper():
            score += 5
        
        return min(100, max(0, score))
    
    def _score_hashtag_strategy(self, hashtags: List[Dict], platform: str) -> int:
        """Score hashtag strategy"""
        if not hashtags:
            return 0
        
        score = 50
        count = len(hashtags)
        
        if platform == 'Twitter':
            if 1 <= count <= 3:
                score += 25
            else:
                score -= 15
        else:
            if 8 <= count <= 15:
                score += 25
            elif 5 <= count < 8:
                score += 15
        
        avg_relevance = sum(h['relevance'] for h in hashtags) / len(hashtags)
        score += int((avg_relevance - 50) / 2)
        
        data_backed = sum(1 for h in hashtags if '[✓ Data:' in h['reason'])
        score += min(15, data_backed * 5)
        
        return min(100, max(0, score))
    
    def _score_timing(self, text: str) -> int:
        """Score timing relevance"""
        score = 60
        
        timely_keywords = ['new', 'now', 'today', 'breaking', 'update', 'trending']
        if any(keyword in text.lower() for keyword in timely_keywords):
            score += 20
        
        day = datetime.now().weekday()
        if day in [1, 2, 3]:
            score += 10
        
        return min(100, score)
    
    def _calculate_data_confidence(self, insights: Dict) -> int:
        """Calculate confidence based on available data"""
        if insights['tracked_posts'] == 0:
            return 30
        elif insights['tracked_posts'] < 10:
            return 50
        elif insights['tracked_posts'] < 50:
            return 75
        else:
            return 95
    
    def _generate_insights_with_learning(self, text: str, platform: str,
                                        scores: Dict, insights: Dict) -> List[str]:
        """Generate insights informed by data"""
        result = []
        
        if scores['data_confidence'] >= 75:
            result.append(f"🎓 High Confidence: Based on {insights['tracked_posts']} tracked posts")
        elif scores['data_confidence'] >= 50:
            result.append(f"📊 Growing Dataset: Learning from {insights['tracked_posts']} posts")
        else:
            result.append("🌱 Building Knowledge: Track posts to unlock insights!")
        
        if insights.get('optimal_length'):
            current_len = len(text)
            optimal_len = insights['optimal_length']
            if abs(current_len - optimal_len) > 100:
                result.append(f"📏 Data shows ~{optimal_len} chars perform best on {platform}")
        
        if insights.get('best_hashtag'):
            result.append(f"🏆 Top performer: #{insights['best_hashtag']['tag']} "
                         f"({insights['best_hashtag']['engagement']:.1f}% avg)")
        
        if scores['engagement_potential'] >= 80:
            result.append("🎯 Excellent! Optimized for high engagement")
        elif scores['engagement_potential'] >= 65:
            result.append("👍 Good post! Minor tweaks could help")
        else:
            result.append("🔧 Needs optimization for better engagement")
        
        return result

def display_score_gauge(score: int, label: str, subtitle: str = ""):
    """Display score as a visual gauge"""
    color = '#4CAF50' if score >= 75 else '#FFC107' if score >= 50 else '#F44336'
    
    subtitle_display = f"<div style='font-size: 0.85rem; color: #999; margin-top: 0.25rem;'>{subtitle}</div>" if subtitle else ""
    
    st.markdown(f"""
        <div style='text-align: center; margin: 1rem 0;'>
            <div style='font-size: 3rem; font-weight: bold; color: {color};'>
                {score}
            </div>
            <div style='font-size: 1rem; color: #666;'>{label}</div>
            {subtitle_display}
            <div style='background: #e0e0e0; height: 10px; border-radius: 5px; margin-top: 0.5rem;'>
                <div style='background: {color}; height: 100%; width: {score}%; border-radius: 5px;'></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def main():
    st.markdown("<h1 class='main-header'>🚀 AI Hashtag Optimizer Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>AI recommendations that learn from real performance data</p>", unsafe_allow_html=True)
    
    ollama = OllamaAPI()
    db = PerformanceDatabase()
    
    if not ollama.is_available():
        st.error("⚠️ Ollama is not running!")
        st.info("Install: https://ollama.ai\nRun: `ollama pull llama3.2:3b`")
        return
    
    tab1, tab2, tab3 = st.tabs(["📝 Analyze Post", "📊 Track Performance", "📈 Insights Dashboard"])
    
    with tab1:
        analyze_tab(ollama, db)
    
    with tab2:
        tracking_tab(db)
    
    with tab3:
        insights_dashboard(db)

def analyze_tab(ollama, db):
    """Main analysis tab"""
    st.success("✅ Ollama is running!")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        platform = st.selectbox("Platform", ["Twitter", "Instagram"])
        user_text = st.text_area(
            "Your Post Content:",
            height=150,
            placeholder=f"Write your {platform} post here..."
        )
        analyze_button = st.button("🔍 Analyze with AI", type="primary", use_container_width=True)
    
    with col2:
        st.subheader("📏 Stats")
        if user_text:
            st.metric("Characters", len(user_text))
            st.metric("Words", len(user_text.split()))
    
    if analyze_button and user_text:
        with st.spinner("🧠 AI analyzing..."):
            analyzer = EnhancedHashtagAnalyzer(ollama, db)
            results = analyzer.analyze_content(user_text, platform)
        
        st.markdown("---")
        st.subheader("📊 Performance Analysis")
        
        cols = st.columns(4)
        scores = results['performance_score']
        
        with cols[0]:
            confidence_label = "🎓 High" if scores['data_confidence'] >= 75 else "📊 Medium" if scores['data_confidence'] >= 50 else " Quality"
            display_score_gauge(scores['content_quality'], "Predicted Score", confidence_label)
        with cols[1]:
            confidence_label = "🎓 High" if scores['data_confidence'] >= 75 else "📊 Medium" if scores['data_confidence'] >= 50 else " Hashtag Strategy"
            display_score_gauge(scores['hashtag_strategy'], "Predicted Score", confidence_label)
        with cols[2]:
            confidence_label = "🎓 High" if scores['data_confidence'] >= 75 else "📊 Medium" if scores['data_confidence'] >= 50 else " Timing"
            display_score_gauge(scores['timing_relevance'], "Predicted Score", confidence_label)
        with cols[3]:
            confidence_label = "🎓 High" if scores['data_confidence'] >= 75 else "📊 Medium" if scores['data_confidence'] >= 50 else " Building"
            display_score_gauge(scores['engagement_potential'], "Predicted Score", confidence_label)
        
        st.markdown("---")
        st.subheader("🏷️ Recommended Hashtags")
        
        hashtag_string = " ".join([f"{h['tag']}" for h in results['hashtags']])
        st.code(hashtag_string, language=None)
        
        col_a, col_b = st.columns([2, 1])
        
        with col_a:
            for tag in results['hashtags']:
                with st.expander(f"{tag['tag']} - Relevance: {tag['relevance']}%"):
                    st.write(f"**Popularity:** {tag['popularity']}")
                    st.write(f"**Why:** {tag['reason']}")
        
        with col_b:
            if results.get('similar_posts'):
                st.markdown("### 🎯 Similar High-Performers")
                for post in results['similar_posts'][:3]:
                    st.info(f"**{post['engagement_rate']:.1f}% engagement**\n\n{post['content']}")
        
        st.markdown("---")
        st.subheader("💡 AI Insights")
        for insight in results['insights']:
            st.info(insight)
        
        st.session_state['last_post_id'] = results['post_id']
        st.success(f"✅ Prediction saved! Post ID: {results['post_id']}")

def tracking_tab(db):
    """Performance tracking tab"""
    st.subheader("📊 Track Your Post Performance")
    st.info("💡 Update predictions with actual metrics to help the AI learn!")
    
    post_id = st.number_input("Post ID", min_value=1, value=st.session_state.get('last_post_id', 1))
    
    col1, col2 = st.columns(2)
    
    with col1:
        likes = st.number_input("Likes", min_value=0, value=0)
        comments = st.number_input("Comments", min_value=0, value=0)
    
    with col2:
        shares = st.number_input("Shares/Retweets", min_value=0, value=0)
        impressions = st.number_input("Impressions/Reach", min_value=0, value=0)
    
    if st.button("💾 Save Performance Data", type="primary", use_container_width=True):
        if impressions > 0:
            db.update_actual_performance(post_id, likes, comments, shares, impressions)
            engagement_rate = ((likes + comments + shares) / impressions) * 100
            
            st.markdown(f"""
                <div class='success-box'>
                    <h3>✅ Performance Data Saved!</h3>
                    <p><strong>Engagement Rate:</strong> {engagement_rate:.2f}%</p>
                    <p>The AI will use this data to improve recommendations!</p>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.error("Please enter impressions greater than 0")
    
    st.markdown("---")
    st.markdown("### 📖 How to Find These Metrics")
    
    with st.expander("Twitter/X Analytics"):
        st.markdown("""
        1. Click on your tweet
        2. Click 'View post analytics'
        3. Find impressions and engagement metrics
        """)
    
    with st.expander("Instagram Insights"):
        st.markdown("""
        1. Go to your post
        2. Tap 'View Insights'
        3. Find reach and engagement metrics
        """)

def insights_dashboard(db):
    """Analytics dashboard tab"""
    st.subheader("📈 Learning Dashboard")
    
    platform = st.selectbox("Select Platform", ["Twitter", "Instagram"], key="dash_platform")
    
    insights = db.get_learning_insights(platform)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Posts", insights['total_posts'])
    with col2:
        st.metric("Tracked", insights['tracked_posts'])
    with col3:
        if insights.get('avg_engagement'):
            st.metric("Avg Engagement", f"{insights['avg_engagement']:.2f}%")
        else:
            st.metric("Avg Engagement", "N/A")
    with col4:
        confidence = "High 🎓" if insights['tracked_posts'] >= 50 else "Medium 📊" if insights['tracked_posts'] >= 10 else "Building 🌱"
        st.metric("Confidence", confidence)
    
    st.markdown("---")
    st.subheader("🏆 Top Performing Hashtags")
    
    top_hashtags = db.get_top_hashtags(platform, limit=20)
    
    if top_hashtags:
        try:
            import pandas as pd
            df = pd.DataFrame(top_hashtags)
            df['hashtag'] = df['hashtag'].apply(lambda x: f"#{x}")
            df['avg_engagement'] = df['avg_engagement'].apply(lambda x: f"{x:.2f}%")
            
            st.dataframe(
                df[['hashtag', 'total_uses', 'avg_engagement']],
                use_container_width=True,
                hide_index=True
            )
            
            if len(top_hashtags) >= 5:
                st.markdown("### 📊 Top 10 by Engagement")
                chart_data = pd.DataFrame({
                    'Hashtag': [f"#{h['hashtag']}" for h in top_hashtags[:10]],
                    'Engagement': [h['avg_engagement'] for h in top_hashtags[:10]]
                })
                st.bar_chart(chart_data.set_index('Hashtag'))
        except ImportError:
            for tag in top_hashtags[:10]:
                st.write(f"**#{tag['hashtag']}**: {tag['avg_engagement']:.2f}% avg ({tag['total_uses']} uses)")
    else:
        st.info("📝 No performance data yet. Start tracking posts!")
    
    st.markdown("---")
    st.subheader("💡 Learned Best Practices")
    
    if insights.get('optimal_length'):
        st.success(f"📏 **Optimal Length:** {insights['optimal_length']} characters")
    
    if insights.get('best_hashtag'):
        st.success(f"🏆 **Star Hashtag:** #{insights['best_hashtag']['tag']} ({insights['best_hashtag']['engagement']:.2f}%)")
    
    if insights['tracked_posts'] >= 10:
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                AVG(CASE WHEN p.has_question = 1 THEN perf.engagement_rate ELSE NULL END) as with_q,
                AVG(CASE WHEN p.has_question = 0 THEN perf.engagement_rate ELSE NULL END) as without_q
            FROM posts p
            JOIN performance perf ON p.id = perf.post_id
            WHERE p.platform = ?
        """, (platform,))
        
        q_data = cursor.fetchone()
        if q_data[0] and q_data[1]:
            diff = q_data[0] - q_data[1]
            if abs(diff) > 0.5:
                emoji = "✅" if diff > 0 else "⚠️"
                st.info(f"{emoji} Questions: {q_data[0]:.2f}% vs No questions: {q_data[1]:.2f}%")
        
        cursor.execute("""
            SELECT 
                AVG(CASE WHEN p.has_emoji = 1 THEN perf.engagement_rate ELSE NULL END) as with_e,
                AVG(CASE WHEN p.has_emoji = 0 THEN perf.engagement_rate ELSE NULL END) as without_e
            FROM posts p
            JOIN performance perf ON p.id = perf.post_id
            WHERE p.platform = ?
        """, (platform,))
        
        e_data = cursor.fetchone()
        if e_data[0] and e_data[1]:
            diff = e_data[0] - e_data[1]
            if abs(diff) > 0.5:
                emoji_icon = "✅" if diff > 0 else "⚠️"
                st.info(f"{emoji_icon} Emojis: {e_data[0]:.2f}% vs No emojis: {e_data[1]:.2f}%")
        
        conn.close()
    
    st.markdown("---")
    st.subheader("💾 Export Data")
    
    if st.button("📥 Export to CSV"):
        try:
            import pandas as pd
            conn = sqlite3.connect(db.db_path)
            
            query = """
                SELECT 
                    p.id, p.platform, p.content, p.created_at, p.predicted_score,
                    perf.likes, perf.comments, perf.shares, perf.impressions, 
                    perf.engagement_rate,
                    GROUP_CONCAT(h.hashtag, ', ') as hashtags
                FROM posts p
                LEFT JOIN performance perf ON p.id = perf.post_id
                LEFT JOIN hashtags h ON p.id = h.post_id
                WHERE p.platform = ?
                GROUP BY p.id
                ORDER BY p.created_at DESC
            """
            
            df = pd.read_sql_query(query, conn, params=(platform,))
            conn.close()
            
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"{platform}_performance.csv",
                mime="text/csv"
            )
        except Exception as e:
            st.error(f"Export failed: {str(e)}")

if __name__ == "__main__":
    main()