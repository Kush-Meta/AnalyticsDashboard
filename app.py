import streamlit as st
import requests
import json
import re
from typing import List, Dict, Tuple
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Social Hashtag Optimizer",
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
    .metric-card {
        background: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .hashtag-badge {
        display: inline-block;
        background: #667eea;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        margin: 0.3rem;
        font-weight: 500;
    }
    </style>
""", unsafe_allow_html=True)

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

class HashtagAnalyzer:
    """Main analyzer for hashtags and performance scoring"""
    
    def __init__(self, ollama: OllamaAPI):
        self.ollama = ollama
    
    def analyze_content(self, text: str, platform: str) -> Dict:
        """Analyze content and generate hashtags with scoring"""
        
        # Generate hashtags
        hashtags = self._generate_hashtags(text, platform)
        
        # Score the post
        performance_score = self._score_performance(text, hashtags, platform)
        
        # Get insights
        insights = self._generate_insights(text, platform, performance_score)
        
        return {
            'hashtags': hashtags,
            'performance_score': performance_score,
            'insights': insights
        }
    
    def _generate_hashtags(self, text: str, platform: str) -> List[Dict[str, any]]:
        """Generate relevant hashtags using LLM"""
        
        platform_context = {
            'Twitter': 'Twitter posts perform best with 1-3 highly relevant hashtags. Focus on trending and niche-specific tags.',
            'Instagram': 'Instagram posts can use 8-15 hashtags effectively. Mix popular, medium, and niche hashtags for best reach.'
        }
        
        system_prompt = f"""You are a social media expert specializing in {platform} hashtag strategy. 
{platform_context[platform]}

Your task is to analyze content and suggest hashtags that will maximize engagement and reach."""

        prompt = f"""Analyze this {platform} post and suggest hashtags:

Post: "{text}"

Provide exactly {'3' if platform == 'Twitter' else '12'} hashtags ranked by effectiveness. For each hashtag:
1. The hashtag itself (without #)
2. A relevance score (0-100)
3. Estimated popularity (High/Medium/Low)
4. Brief reason why it works

Format your response as JSON array:
[
  {{"tag": "example", "relevance": 95, "popularity": "High", "reason": "brief explanation"}},
  ...
]

Only return the JSON array, nothing else."""

        response = self.ollama.generate(prompt, system_prompt)
        
        if response:
            try:
                # Extract JSON from response
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    hashtags = json.loads(json_match.group())
                    return hashtags
            except:
                pass
        
        # Fallback hashtags if LLM fails
        return self._fallback_hashtags(text, platform)
    
    def _fallback_hashtags(self, text: str, platform: str) -> List[Dict]:
        """Fallback hashtag generation using keyword extraction"""
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        common_words = {'this', 'that', 'with', 'from', 'have', 'been', 'were', 'their', 'would'}
        keywords = [w for w in words if w not in common_words][:5]
        
        hashtags = []
        for i, word in enumerate(keywords):
            hashtags.append({
                'tag': word,
                'relevance': 90 - (i * 10),
                'popularity': 'Medium',
                'reason': 'Extracted from content keywords'
            })
        
        return hashtags
    
    def _score_performance(self, text: str, hashtags: List[Dict], platform: str) -> Dict:
        """Score the post's potential performance"""
        
        scores = {
            'content_quality': self._score_content_quality(text, platform),
            'hashtag_strategy': self._score_hashtag_strategy(hashtags, platform),
            'timing_relevance': self._score_timing(text),
            'engagement_potential': 0
        }
        
        # Calculate overall engagement potential
        scores['engagement_potential'] = int(
            scores['content_quality'] * 0.4 +
            scores['hashtag_strategy'] * 0.35 +
            scores['timing_relevance'] * 0.25
        )
        
        return scores
    
    def _score_content_quality(self, text: str, platform: str) -> int:
        """Score content quality based on best practices"""
        score = 50  # Base score
        
        text_length = len(text)
        
        # Length optimization
        if platform == 'Twitter':
            if 100 <= text_length <= 280:
                score += 20
            elif text_length > 280:
                score -= 10
        else:  # Instagram
            if 138 <= text_length <= 2200:
                score += 20
        
        # Engagement elements
        if '?' in text:
            score += 10  # Questions increase engagement
        if any(emoji in text for emoji in '😊🔥💯❤️👍🎉'):
            score += 10
        if text[0].isupper() or text.startswith('"'):
            score += 5  # Strong opening
        
        # Readability
        sentences = text.split('.')
        if 1 <= len(sentences) <= 4:
            score += 5
        
        return min(100, max(0, score))
    
    def _score_hashtag_strategy(self, hashtags: List[Dict], platform: str) -> int:
        """Score hashtag strategy effectiveness"""
        if not hashtags:
            return 0
        
        score = 50
        
        # Number of hashtags
        count = len(hashtags)
        if platform == 'Twitter':
            if 1 <= count <= 3:
                score += 25
            else:
                score -= 15
        else:  # Instagram
            if 8 <= count <= 15:
                score += 25
            elif 5 <= count < 8:
                score += 15
        
        # Relevance average
        avg_relevance = sum(h['relevance'] for h in hashtags) / len(hashtags)
        score += int((avg_relevance - 50) / 2)
        
        # Diversity in popularity
        popularities = [h['popularity'] for h in hashtags]
        if len(set(popularities)) > 1:
            score += 10  # Good mix
        
        return min(100, max(0, score))
    
    def _score_timing(self, text: str) -> int:
        """Score based on trending topics and timing"""
        score = 60  # Base score
        
        # Check for time-sensitive keywords
        timely_keywords = ['new', 'now', 'today', 'breaking', 'update', 'trending']
        if any(keyword in text.lower() for keyword in timely_keywords):
            score += 20
        
        # Day of week consideration (simplified)
        day = datetime.now().weekday()
        if day in [1, 2, 3]:  # Tue, Wed, Thu - best posting days
            score += 10
        
        return min(100, score)
    
    def _generate_insights(self, text: str, platform: str, scores: Dict) -> List[str]:
        """Generate actionable insights"""
        insights = []
        
        # Content quality insights
        if scores['content_quality'] < 60:
            insights.append("💡 Consider adding a question or call-to-action to boost engagement")
        
        if len(text) < 50:
            insights.append("📝 Your post is quite short - adding more context could improve performance")
        
        # Hashtag insights
        if scores['hashtag_strategy'] < 70:
            if platform == 'Twitter':
                insights.append("🏷️ For Twitter, use 1-3 highly targeted hashtags for best results")
            else:
                insights.append("🏷️ Instagram performs better with 8-15 relevant hashtags")
        
        # Timing insights
        if scores['timing_relevance'] < 70:
            insights.append("⏰ Consider posting during peak hours (10am-3pm) for better visibility")
        
        # Overall performance
        if scores['engagement_potential'] >= 80:
            insights.append("🎯 Excellent! This post is optimized for high engagement")
        elif scores['engagement_potential'] >= 65:
            insights.append("👍 Good post! Minor tweaks could boost performance further")
        else:
            insights.append("🔧 This post needs optimization to maximize engagement")
        
        return insights

def display_score_gauge(score: int, label: str):
    """Display score as a visual gauge"""
    color = '#4CAF50' if score >= 75 else '#FFC107' if score >= 50 else '#F44336'
    
    st.markdown(f"""
        <div style='text-align: center; margin: 1rem 0;'>
            <div style='font-size: 3rem; font-weight: bold; color: {color};'>
                {score}
            </div>
            <div style='font-size: 1rem; color: #666;'>{label}</div>
            <div style='background: #e0e0e0; height: 10px; border-radius: 5px; margin-top: 0.5rem;'>
                <div style='background: {color}; height: 100%; width: {score}%; border-radius: 5px;'></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# Main App
def main():
    st.markdown("<h1 class='main-header'>🚀 Social Hashtag Optimizer</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666; margin-bottom: 2rem;'>AI-powered hashtag recommendations with performance predictions</p>", unsafe_allow_html=True)
    
    # Initialize Ollama
    ollama = OllamaAPI()
    
    # Check Ollama status
    if not ollama.is_available():
        st.error("⚠️ Ollama is not running! Please start Ollama first.")
        st.info("""
        **Setup Instructions:**
        1. Install Ollama from https://ollama.ai
        2. Run: `ollama pull llama3.2:3b`
        3. Ollama will start automatically
        4. Refresh this page
        """)
        return
    
    st.success("✅ Ollama is running!")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        platform = st.selectbox(
            "Platform",
            ["Twitter", "Instagram"],
            help="Choose your target platform"
        )
        
        st.markdown("---")
        st.markdown("### 📊 About Scores")
        st.markdown("""
        - **Content Quality**: Writing, length, engagement hooks
        - **Hashtag Strategy**: Relevance, count, diversity
        - **Timing Relevance**: Trending topics, posting time
        - **Engagement Potential**: Overall predicted performance
        """)
    
    # Main input
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"✍️ Your {platform} Post")
        user_text = st.text_area(
            "Enter your post content:",
            height=150,
            placeholder=f"Write your {platform} post here..."
        )
        
        analyze_button = st.button("🔍 Analyze & Generate Hashtags", type="primary", use_container_width=True)
    
    with col2:
        st.subheader("📏 Post Stats")
        if user_text:
            st.metric("Characters", len(user_text))
            st.metric("Words", len(user_text.split()))
            
            if platform == "Twitter":
                remaining = 280 - len(user_text)
                st.metric("Remaining", remaining, delta=remaining)
    
    # Analysis
    if analyze_button and user_text:
        with st.spinner("🧠 AI is analyzing your post..."):
            analyzer = HashtagAnalyzer(ollama)
            results = analyzer.analyze_content(user_text, platform)
        
        st.markdown("---")
        
        # Performance Scores
        st.subheader("📊 Performance Analysis")
        
        cols = st.columns(4)
        scores = results['performance_score']
        
        with cols[0]:
            display_score_gauge(scores['content_quality'], "Content Quality")
        with cols[1]:
            display_score_gauge(scores['hashtag_strategy'], "Hashtag Strategy")
        with cols[2]:
            display_score_gauge(scores['timing_relevance'], "Timing Relevance")
        with cols[3]:
            display_score_gauge(scores['engagement_potential'], "Engagement Potential")
        
        # Hashtag Recommendations
        st.markdown("---")
        st.subheader("🏷️ Recommended Hashtags")
        
        hashtag_col1, hashtag_col2 = st.columns([2, 1])
        
        with hashtag_col1:
            st.markdown("### Copy These Hashtags:")
            hashtag_string = " ".join([f"#{h['tag']}" for h in results['hashtags']])
            st.code(hashtag_string, language=None)
            
            st.markdown("### Individual Hashtags:")
            for i, tag in enumerate(results['hashtags'], 1):
                with st.expander(f"#{tag['tag']} - {tag['popularity']} Popularity"):
                    col_a, col_b = st.columns([1, 2])
                    with col_a:
                        st.metric("Relevance", f"{tag['relevance']}%")
                    with col_b:
                        st.write(f"**Why it works:** {tag['reason']}")
        
        with hashtag_col2:
            st.markdown("### Quick Stats")
            st.info(f"**Total Hashtags:** {len(results['hashtags'])}")
            
            high_relevance = sum(1 for h in results['hashtags'] if h['relevance'] >= 80)
            st.success(f"**High Relevance:** {high_relevance}")
            
            avg_relevance = sum(h['relevance'] for h in results['hashtags']) / len(results['hashtags'])
            st.metric("Avg Relevance", f"{avg_relevance:.1f}%")
        
        # Insights
        st.markdown("---")
        st.subheader("💡 AI Insights & Recommendations")
        
        for insight in results['insights']:
            st.info(insight)
        
        # Final recommendations
        if scores['engagement_potential'] < 70:
            st.markdown("### 🎯 Quick Wins to Improve Your Score:")
            improvements = []
            
            if scores['content_quality'] < 70:
                improvements.append("- Add a compelling question or call-to-action")
                improvements.append("- Include relevant emojis to increase visual appeal")
            
            if scores['hashtag_strategy'] < 70:
                if platform == 'Twitter':
                    improvements.append("- Reduce to 2-3 most relevant hashtags")
                else:
                    improvements.append("- Add more hashtags (aim for 10-15)")
            
            if improvements:
                for imp in improvements:
                    st.markdown(imp)

if __name__ == "__main__":
    main()