#!/usr/bin/env python3
"""
Historical Data Importer for Hashtag Optimizer
Import past post performance data from CSV to train your AI
"""

import sqlite3
import csv
import sys
import re
from datetime import datetime
from typing import List, Dict

class DataImporter:
    def __init__(self, db_path: str = "hashtag_performance.db"):
        self.db_path = db_path
        self.imported_count = 0
        self.skipped_count = 0
        self.errors = []
    
    def import_from_csv(self, csv_file: str):
        """Import historical data from CSV file"""
        print(f"📂 Reading data from {csv_file}...")
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Validate headers
                required_fields = ['platform', 'content', 'likes', 'comments', 
                                 'shares', 'impressions']
                if not all(field in reader.fieldnames for field in required_fields):
                    print(f"❌ Error: CSV must have these columns: {', '.join(required_fields)}")
                    print(f"   Found: {', '.join(reader.fieldnames)}")
                    return False
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                for i, row in enumerate(reader, 1):
                    try:
                        self._import_row(cursor, row, i)
                    except Exception as e:
                        self.errors.append(f"Row {i}: {str(e)}")
                        self.skipped_count += 1
                
                conn.commit()
                conn.close()
                
                self._print_summary()
                return True
                
        except FileNotFoundError:
            print(f"❌ Error: File '{csv_file}' not found")
            return False
        except Exception as e:
            print(f"❌ Error reading CSV: {str(e)}")
            return False
    
    def _import_row(self, cursor, row: Dict, row_num: int):
        """Import a single row"""
        # Validate required fields
        platform = row['platform'].strip()
        if platform not in ['Twitter', 'Instagram']:
            raise ValueError(f"Platform must be 'Twitter' or 'Instagram', got '{platform}'")
        
        content = row['content'].strip()
        if not content:
            raise ValueError("Content cannot be empty")
        
        # Parse metrics
        try:
            likes = int(row['likes'])
            comments = int(row['comments'])
            shares = int(row['shares'])
            impressions = int(row['impressions'])
        except ValueError:
            raise ValueError("Likes, comments, shares, and impressions must be numbers")
        
        if impressions <= 0:
            raise ValueError("Impressions must be greater than 0")
        
        # Parse hashtags from content or dedicated column
        hashtags = self._extract_hashtags(content)
        if 'hashtags' in row and row['hashtags']:
            # Additional hashtags from column
            extra_tags = [tag.strip().lstrip('#') for tag in row['hashtags'].split(',')]
            hashtags.extend(extra_tags)
        
        hashtags = list(set(hashtags))  # Remove duplicates
        
        # Analyze content features
        content_length = len(content)
        has_question = 1 if '?' in content else 0
        has_emoji = 1 if any(emoji in content for emoji in '😊🔥💯❤️👍🎉✨💪🙌🎯💡📊🚀') else 0
        
        # Calculate engagement rate
        engagement_rate = ((likes + comments + shares) / impressions) * 100
        
        # Estimate a "predicted score" based on simple heuristics
        # This is what the AI would have predicted before learning
        predicted_score = self._estimate_baseline_score(content, platform, len(hashtags))
        
        # Get or create date
        created_at = row.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        # Insert post
        cursor.execute("""
            INSERT INTO posts (platform, content, content_length, has_question, 
                             has_emoji, predicted_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (platform, content, content_length, has_question, has_emoji, 
              predicted_score, created_at))
        
        post_id = cursor.lastrowid
        
        # Insert hashtags
        for tag in hashtags:
            cursor.execute("""
                INSERT INTO hashtags (post_id, hashtag, predicted_relevance)
                VALUES (?, ?, ?)
            """, (post_id, tag, 85))  # Default relevance
        
        # Insert performance
        cursor.execute("""
            INSERT INTO performance (post_id, likes, comments, shares, 
                                   impressions, engagement_rate, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (post_id, likes, comments, shares, impressions, engagement_rate, created_at))
        
        # Update hashtag stats
        for tag in hashtags:
            cursor.execute("""
                INSERT INTO hashtag_stats (hashtag, platform, total_uses, 
                                         avg_engagement, last_used)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(hashtag) DO UPDATE SET
                    total_uses = total_uses + 1,
                    avg_engagement = (avg_engagement * (total_uses - 1) + ?) / total_uses,
                    last_used = ?
            """, (tag, platform, engagement_rate, created_at, engagement_rate, created_at))
        
        self.imported_count += 1
        
        # Progress indicator
        status_emoji = "🔥" if engagement_rate >= 3.0 else "✅" if engagement_rate >= 1.5 else "📊"
        print(f"{status_emoji} Row {row_num}: {content[:50]}... ({engagement_rate:.2f}% engagement)")
    
    def _extract_hashtags(self, content: str) -> List[str]:
        """Extract hashtags from content"""
        hashtags = re.findall(r'#(\w+)', content)
        return hashtags
    
    def _estimate_baseline_score(self, content: str, platform: str, 
                                 num_hashtags: int) -> int:
        """Estimate what a baseline model would predict"""
        score = 60  # Base score
        
        # Length scoring
        if platform == 'Twitter':
            if 100 <= len(content) <= 280:
                score += 15
        else:
            if 138 <= len(content) <= 2200:
                score += 15
        
        # Hashtag count
        if platform == 'Twitter' and 1 <= num_hashtags <= 3:
            score += 10
        elif platform == 'Instagram' and 8 <= num_hashtags <= 15:
            score += 10
        
        # Engagement elements
        if '?' in content:
            score += 5
        if any(emoji in content for emoji in '😊🔥💯❤️👍🎉'):
            score += 5
        
        return min(100, score)
    
    def _print_summary(self):
        """Print import summary"""
        print("\n" + "="*60)
        print("📊 IMPORT SUMMARY")
        print("="*60)
        print(f"✅ Successfully imported: {self.imported_count} posts")
        print(f"⚠️  Skipped (errors): {self.skipped_count} posts")
        
        if self.errors:
            print("\n⚠️  Errors encountered:")
            for error in self.errors[:10]:  # Show first 10 errors
                print(f"   - {error}")
            if len(self.errors) > 10:
                print(f"   ... and {len(self.errors) - 10} more errors")
        
        print("\n🎉 Import complete! Your AI is now smarter.")
        print("   Run the Streamlit app to see updated insights!")
        print("="*60)

def create_sample_csv():
    """Create a sample CSV file for reference"""
    sample_data = """platform,content,likes,comments,shares,impressions,hashtags,date
Twitter,"Just launched our new product! Check it out 🚀 #startup #innovation #tech",45,8,12,2500,"startup,innovation,tech",2025-09-15
Instagram,"Behind the scenes of our creative process. Swipe to see the journey! 📸 #behindthescenes #creative #process",230,15,20,5800,"behindthescenes,creative,process,photography",2025-09-16
Twitter,"Hot take: AI will transform content creation in ways we can't imagine yet 🤖",89,25,18,3200,"AI,contentcreation,future",2025-09-17
Instagram,"New blog post is live! Link in bio. Sharing our top tips for social media growth 📈 #socialmedia #marketing #tips",180,12,15,4200,"socialmedia,marketing,tips,growth,contentmarketing",2025-09-18
Twitter,"Question for my followers: What's your biggest challenge with content creation? 🤔",35,42,8,1800,"content,question,community",2025-09-19
"""
    
    with open('sample_import.csv', 'w') as f:
        f.write(sample_data)
    
    print("✅ Created sample_import.csv")
    print("   Edit this file with your own data, then run:")
    print("   python import_historical_data.py sample_import.csv")

def main():
    print("╔════════════════════════════════════════════════════════╗")
    print("║   📊 Historical Data Importer for Hashtag Optimizer   ║")
    print("╚════════════════════════════════════════════════════════╝")
    print()
    
    if len(sys.argv) < 2:
        print("Usage: python import_historical_data.py <csv_file>")
        print()
        print("Options:")
        print("  python import_historical_data.py sample    - Create sample CSV")
        print("  python import_historical_data.py data.csv  - Import from CSV")
        print()
        print("CSV Format Required:")
        print("  platform,content,likes,comments,shares,impressions,hashtags,date")
        print()
        print("Example:")
        print('  Twitter,"My post text",45,8,12,2500,"tech,ai",2025-09-15')
        sys.exit(1)
    
    if sys.argv[1] == 'sample':
        create_sample_csv()
        sys.exit(0)
    
    csv_file = sys.argv[1]
    importer = DataImporter()
    
    success = importer.import_from_csv(csv_file)
    
    if success and importer.imported_count > 0:
        print("\n💡 Next Steps:")
        print("   1. Run: streamlit run app.py")
        print("   2. Go to 'Insights Dashboard' tab")
        print("   3. See your learned patterns and top hashtags!")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()