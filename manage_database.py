#!/usr/bin/env python3
"""
Database Management Utility for Hashtag Optimizer
Backup, restore, analyze, and clean your performance database
"""

import sqlite3
import sys
import shutil
from datetime import datetime
from pathlib import Path

class DatabaseManager:
    def __init__(self, db_path: str = "hashtag_performance.db"):
        self.db_path = db_path
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
    
    def backup(self) -> str:
        """Create a backup of the database"""
        if not Path(self.db_path).exists():
            print(f"❌ Database not found: {self.db_path}")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"hashtag_performance_{timestamp}.db"
        
        shutil.copy2(self.db_path, backup_path)
        
        # Get database size
        size_mb = Path(backup_path).stat().st_size / (1024 * 1024)
        
        print(f"✅ Backup created successfully!")
        print(f"   Location: {backup_path}")
        print(f"   Size: {size_mb:.2f} MB")
        
        return str(backup_path)
    
    def restore(self, backup_path: str):
        """Restore database from backup"""
        if not Path(backup_path).exists():
            print(f"❌ Backup file not found: {backup_path}")
            return False
        
        # Backup current database first
        if Path(self.db_path).exists():
            self.backup()
            print("   (Created backup of current database)")
        
        shutil.copy2(backup_path, self.db_path)
        print(f"✅ Database restored from {backup_path}")
        return True
    
    def list_backups(self):
        """List all available backups"""
        backups = sorted(self.backup_dir.glob("hashtag_performance_*.db"), reverse=True)
        
        if not backups:
            print("📂 No backups found")
            return
        
        print("📂 Available Backups:")
        print("="*60)
        
        for i, backup in enumerate(backups, 1):
            size_mb = backup.stat().st_size / (1024 * 1024)
            modified = datetime.fromtimestamp(backup.stat().st_mtime)
            print(f"{i}. {backup.name}")
            print(f"   Size: {size_mb:.2f} MB | Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def stats(self):
        """Show database statistics"""
        if not Path(self.db_path).exists():
            print(f"❌ Database not found: {self.db_path}")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        print("📊 Database Statistics")
        print("="*60)
        
        # Total posts
        cursor.execute("SELECT COUNT(*) FROM posts")
        total_posts = cursor.fetchone()[0]
        print(f"Total Posts Analyzed: {total_posts}")
        
        # Posts by platform
        cursor.execute("""
            SELECT platform, COUNT(*) 
            FROM posts 
            GROUP BY platform
        """)
        print("\nPosts by Platform:")
        for platform, count in cursor.fetchall():
            print(f"  - {platform}: {count}")
        
        # Tracked posts
        cursor.execute("SELECT COUNT(*) FROM performance")
        tracked = cursor.fetchone()[0]
        print(f"\nPosts with Performance Data: {tracked}")
        
        if tracked > 0:
            # Average engagement
            cursor.execute("SELECT AVG(engagement_rate) FROM performance")
            avg_engagement = cursor.fetchone()[0]
            print(f"Average Engagement Rate: {avg_engagement:.2f}%")
            
            # Best performing post
            cursor.execute("""
                SELECT p.content, perf.engagement_rate 
                FROM posts p
                JOIN performance perf ON p.id = perf.post_id
                ORDER BY perf.engagement_rate DESC
                LIMIT 1
            """)
            best_post = cursor.fetchone()
            if best_post:
                print(f"\nBest Performing Post:")
                print(f"  Content: {best_post[0][:60]}...")
                print(f"  Engagement: {best_post[1]:.2f}%")
        
        # Unique hashtags
        cursor.execute("SELECT COUNT(DISTINCT hashtag) FROM hashtags")
        unique_hashtags = cursor.fetchone()[0]
        print(f"\nUnique Hashtags Used: {unique_hashtags}")
        
        # Top hashtags
        cursor.execute("""
            SELECT hashtag, total_uses, avg_engagement
            FROM hashtag_stats
            WHERE total_uses >= 2
            ORDER BY avg_engagement DESC
            LIMIT 5
        """)
        top_hashtags = cursor.fetchall()
        
        if top_hashtags:
            print("\nTop 5 Hashtags:")
            for tag, uses, engagement in top_hashtags:
                print(f"  #{tag}: {engagement:.2f}% avg engagement ({uses} uses)")
        
        # Database size
        size_mb = Path(self.db_path).stat().st_size / (1024 * 1024)
        print(f"\nDatabase Size: {size_mb:.2f} MB")
        
        conn.close()
        print("="*60)
    
    def clean_old_predictions(self, days: int = 30):
        """Remove old predictions without performance data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Find old predictions without performance tracking
        cursor.execute("""
            SELECT COUNT(*)
            FROM posts p
            LEFT JOIN performance perf ON p.id = perf.post_id
            WHERE perf.post_id IS NULL
            AND datetime(p.created_at) < datetime('now', ?)
        """, (f'-{days} days',))
        
        count = cursor.fetchone()[0]
        
        if count == 0:
            print(f"✨ No predictions older than {days} days to clean")
            conn.close()
            return
        
        print(f"⚠️  Found {count} predictions older than {days} days without tracking")
        confirm = input("Delete these predictions? (yes/no): ")
        
        if confirm.lower() == 'yes':
            # Delete hashtags first (foreign key)
            cursor.execute("""
                DELETE FROM hashtags
                WHERE post_id IN (
                    SELECT p.id
                    FROM posts p
                    LEFT JOIN performance perf ON p.id = perf.post_id
                    WHERE perf.post_id IS NULL
                    AND datetime(p.created_at) < datetime('now', ?)
                )
            """, (f'-{days} days',))
            
            # Delete posts
            cursor.execute("""
                DELETE FROM posts
                WHERE id NOT IN (SELECT post_id FROM performance)
                AND datetime(created_at) < datetime('now', ?)
            """, (f'-{days} days',))
            
            conn.commit()
            print(f"✅ Cleaned {count} old predictions")
        else:
            print("❌ Cleanup cancelled")
        
        conn.close()
    
    def export_csv(self, output_file: str = "export_data.csv"):
        """Export all data to CSV"""
        if not Path(self.db_path).exists():
            print(f"❌ Database not found: {self.db_path}")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                p.id,
                p.platform,
                p.content,
                p.created_at,
                p.predicted_score,
                perf.likes,
                perf.comments,
                perf.shares,
                perf.impressions,
                perf.engagement_rate,
                GROUP_CONCAT(h.hashtag, ', ') as hashtags
            FROM posts p
            LEFT JOIN performance perf ON p.id = perf.post_id
            LEFT JOIN hashtags h ON p.id = h.post_id
            GROUP BY p.id
            ORDER BY p.created_at DESC
        """)
        
        import csv
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'ID', 'Platform', 'Content', 'Date', 'Predicted Score',
                'Likes', 'Comments', 'Shares', 'Impressions', 
                'Engagement Rate', 'Hashtags'
            ])
            writer.writerows(cursor.fetchall())
        
        conn.close()
        
        print(f"✅ Data exported to {output_file}")
        print(f"   Open in Excel or Google Sheets for analysis")
    
    def vacuum(self):
        """Optimize database (reclaim space after deletions)"""
        if not Path(self.db_path).exists():
            print(f"❌ Database not found: {self.db_path}")
            return
        
        size_before = Path(self.db_path).stat().st_size / (1024 * 1024)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("VACUUM")
        conn.commit()
        conn.close()
        
        size_after = Path(self.db_path).stat().st_size / (1024 * 1024)
        saved = size_before - size_after
        
        print(f"✅ Database optimized!")
        print(f"   Before: {size_before:.2f} MB")
        print(f"   After: {size_after:.2f} MB")
        print(f"   Saved: {saved:.2f} MB")

def main():
    print("╔════════════════════════════════════════════════════╗")
    print("║     💾 Database Manager for Hashtag Optimizer     ║")
    print("╚════════════════════════════════════════════════════╝")
    print()
    
    if len(sys.argv) < 2:
        print("Usage: python manage_database.py <command>")
        print()
        print("Commands:")
        print("  backup              - Create backup of database")
        print("  list                - List all backups")
        print("  restore <file>      - Restore from backup")
        print("  stats               - Show database statistics")
        print("  clean [days]        - Remove old untracked predictions (default: 30 days)")
        print("  export [file]       - Export data to CSV (default: export_data.csv)")
        print("  vacuum              - Optimize database size")
        print()
        print("Examples:")
        print("  python manage_database.py backup")
        print("  python manage_database.py stats")
        print("  python manage_database.py clean 60")
        print("  python manage_database.py export my_data.csv")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    manager = DatabaseManager()
    
    if command == 'backup':
        manager.backup()
    
    elif command == 'list':
        manager.list_backups()
    
    elif command == 'restore':
        if len(sys.argv) < 3:
            print("❌ Please specify backup file")
            print("   Run 'python manage_database.py list' to see available backups")
            sys.exit(1)
        manager.restore(sys.argv[2])
    
    elif command == 'stats':
        manager.stats()
    
    elif command == 'clean':
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        manager.clean_old_predictions(days)
    
    elif command == 'export':
        output_file = sys.argv[2] if len(sys.argv) > 2 else "export_data.csv"
        manager.export_csv(output_file)
    
    elif command == 'vacuum':
        manager.vacuum()
    
    else:
        print(f"❌ Unknown command: {command}")
        print("   Run without arguments to see available commands")
        sys.exit(1)

if __name__ == "__main__":
    main()