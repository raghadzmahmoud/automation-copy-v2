#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎯 News Clustering Service
تجميع الأخبار المتشابهة
"""

import psycopg2
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import List, Dict

from settings import DB_CONFIG
from app.config.user_config import user_config


class NewsClusterer:
    """
    تجميع الأخبار مع دعم:
    1. Incremental clustering
    2. كل خبر = cluster
    3. Smart merge
    """
    
    def __init__(self):
        """الاتصال بقاعدة البيانات"""
        self.conn = None
        self.cursor = None
        
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print("✅ NewsClusterer initialized")
            
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise
        
        # Parameters من user_config
        self.similarity_threshold = user_config.clustering_min_similarity
        self.time_window_hours = user_config.clustering_time_window_hours
        self.min_cluster_size = 1
        
        # تحميل clusters موجودة
        self.existing_clusters = self._load_existing_clusters()
        print(f"   📊 Found {len(self.existing_clusters)} existing clusters")
    
    def _load_existing_clusters(self) -> Dict:
        """تحميل clusters موجودة من DB"""
        clusters = {}
        
        try:
            query = """
                SELECT 
                    nc.id,
                    nc.tags,
                    nc.category_id,
                    nc.created_at,
                    nc.updated_at,
                    array_agg(nci.news_id) as news_ids
                FROM news_clusters nc
                LEFT JOIN news_cluster_members nci ON nc.id = nci.cluster_id
                WHERE nc.created_at >= NOW() - INTERVAL '2 days'
                GROUP BY nc.id, nc.tags, nc.category_id, nc.created_at, nc.updated_at
            """
            
            self.cursor.execute(query)
            rows = self.cursor.fetchall()
            
            for row in rows:
                cluster_id, tags_str, category_id, created_at, updated_at, news_ids = row
                
                tags_set = set(self._parse_tags(tags_str))
                news_ids_set = set(news_ids) if news_ids and news_ids[0] is not None else set()
                
                clusters[cluster_id] = {
                    'tags': tags_set,
                    'category_id': category_id,
                    'news_ids': news_ids_set,
                    'created_at': created_at,
                    'updated_at': updated_at
                }
            
            return clusters
            
        except Exception as e:
            print(f"   ⚠️  Error loading clusters: {e}")
            return {}
    
    def cluster_all_news(self, time_limit_days: int = 2, mode: str = 'incremental') -> Dict:
        """
        تجميع كل الأخبار
        
        Args:
            time_limit_days: عدد الأيام
            mode: 'incremental' أو 'rebuild'
        
        Returns:
            Dict: إحصائيات
        """
        print("\n" + "="*70)
        print(f"🎯 Starting News Clustering ({mode} mode)")
        print("="*70)
        
        # Rebuild mode: حذف القديم
        if mode == 'rebuild':
            print("\n🗑️  Cleaning old clusters...")
            self._clean_old_clusters()
            self.existing_clusters = {}
            print("   ✅ Old clusters removed")
        
        # جلب الأخبار غير المجمعة
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_limit_days)
        news_data = self._fetch_unclustered_news(cutoff_date)
        
        if not news_data:
            print("⚠️  No new news to cluster")
            return {
                'total_news': 0,
                'clusters_created': 0,
                'clusters_updated': 0
            }
        
        print(f"📰 Found {len(news_data)} unclustered news items")
        
        # تجميع حسب Category
        categories_dict = self._group_by_category(news_data)
        print(f"📊 Found {len(categories_dict)} categories")
        
        # Clustering داخل كل category
        total_created = 0
        total_updated = 0
        
        for category_id, category_news in categories_dict.items():
            print(f"\n🔍 Processing Category ID {category_id} ({len(category_news)} news)...")
            
            stats = self._cluster_within_category(category_news, category_id)
            
            total_created += stats['clusters_created']
            total_updated += stats['clusters_updated']
            
            print(f"   ✅ Created: {stats['clusters_created']} | Updated: {stats['clusters_updated']}")
        
        final_stats = {
            'total_news': len(news_data),
            'clusters_created': total_created,
            'clusters_updated': total_updated
        }
        
        print("\n" + "="*70)
        print("🎉 Clustering Complete!")
        print(f"   • Total News: {final_stats['total_news']}")
        print(f"   • Clusters Created: {final_stats['clusters_created']}")
        print(f"   • Clusters Updated: {final_stats['clusters_updated']}")
        print("="*70)
        
        return final_stats
    
    def _fetch_unclustered_news(self, cutoff_date: datetime) -> List[Dict]:
        """جلب الأخبار غير المجمعة"""
        query = """
            SELECT 
                n.id, 
                n.title, 
                n.tags, 
                n.category_id, 
                n.published_at
            FROM raw_news n
            LEFT JOIN news_cluster_members nci ON n.id = nci.news_id
            WHERE n.published_at >= %s
            AND nci.news_id IS NULL
            ORDER BY n.category_id, n.published_at DESC
        """
        
        self.cursor.execute(query, (cutoff_date,))
        rows = self.cursor.fetchall()
        
        news_list = []
        for row in rows:
            news_list.append({
                'id': row[0],
                'title': row[1],
                'tags': self._parse_tags(row[2]),
                'category_id': row[3],
                'published_date': row[4]
            })
        
        return news_list
    
    def _cluster_within_category(self, category_news: List[Dict], category_id: int) -> Dict:
        """تجميع داخل category واحد"""
        stats = {
            'clusters_created': 0,
            'clusters_updated': 0
        }
        
        used_news_ids = set()
        sorted_news = sorted(category_news, key=lambda x: x['published_date'], reverse=True)
        
        for i, anchor_news in enumerate(sorted_news):
            if anchor_news['id'] in used_news_ids:
                continue
            
            anchor_tags = set(anchor_news['tags'])
            
            # فحص cluster موجود
            matching_cluster_id = self._find_matching_cluster(
                anchor_tags,
                category_id,
                anchor_news['published_date']
            )
            
            if matching_cluster_id:
                # إضافة للموجود
                added = self._add_news_to_cluster(matching_cluster_id, [anchor_news['id']])
                if added > 0:
                    stats['clusters_updated'] += 1
                    used_news_ids.add(anchor_news['id'])
                continue
            
            # جمع أخبار مشابهة
            cluster_news_ids = [anchor_news['id']]
            cluster_tags = set(anchor_news['tags'])
            
            for j, candidate_news in enumerate(sorted_news):
                if i == j or candidate_news['id'] in used_news_ids:
                    continue
                
                # فحص Time
                time_diff = abs((anchor_news['published_date'] - candidate_news['published_date']).total_seconds() / 3600)
                if time_diff > self.time_window_hours:
                    continue
                
                # حساب Similarity
                similarity = self._calculate_tag_similarity(
                    anchor_news['tags'],
                    candidate_news['tags']
                )
                
                if similarity >= self.similarity_threshold:
                    cluster_news_ids.append(candidate_news['id'])
                    cluster_tags.update(candidate_news['tags'])
            
            # إنشاء cluster جديد
            success = self._create_new_cluster(
                cluster_news_ids,
                cluster_tags,
                category_id,
                anchor_news['published_date']
            )
            
            if success:
                stats['clusters_created'] += 1
                used_news_ids.update(cluster_news_ids)
        
        return stats
    
    def _find_matching_cluster(self, new_tags: set, category_id: int, news_time: datetime) -> int:
        """البحث عن cluster مشابه"""
        best_match_id = None
        best_similarity = 0.0
        
        for cluster_id, cluster_data in self.existing_clusters.items():
            if cluster_data['category_id'] != category_id:
                continue
            
            cluster_time = cluster_data.get('created_at')
            if cluster_time:
                time_diff = abs((news_time - cluster_time).total_seconds() / 3600)
                if time_diff > self.time_window_hours:
                    continue
            
            similarity = self._calculate_tag_similarity_sets(new_tags, cluster_data['tags'])
            
            if similarity >= self.similarity_threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match_id = cluster_id
        
        return best_match_id
    
    def _add_news_to_cluster(self, cluster_id: int, news_ids: List[int]) -> int:
        """إضافة أخبار لـ cluster موجود مع تحديث updated_at"""
        added_count = 0
        
        try:
            for news_id in news_ids:
                if news_id in self.existing_clusters[cluster_id]['news_ids']:
                    continue
                
                self.cursor.execute("""
                    INSERT INTO news_cluster_members (cluster_id, news_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (cluster_id, news_id))
                
                if self.cursor.rowcount > 0:
                    added_count += 1
                    self.existing_clusters[cluster_id]['news_ids'].add(news_id)
            
            if added_count > 0:
                # ✅ تحديث news_count + updated_at
                now = datetime.now(timezone.utc)
                self.cursor.execute("""
                    UPDATE news_clusters 
                    SET news_count = news_count + %s,
                        updated_at = %s
                    WHERE id = %s
                """, (added_count, now, cluster_id))
                
                # تحديث الـ cache المحلي
                self.existing_clusters[cluster_id]['updated_at'] = now
            
            self.conn.commit()
            return added_count
            
        except Exception as e:
            self.conn.rollback()
            print(f"   ❌ Error adding to cluster: {e}")
            return 0
    
    def _create_new_cluster(self, news_ids: List[int], tags: set, category_id: int, anchor_time: datetime) -> bool:
        """إنشاء cluster جديد"""
        try:
            now = datetime.now(timezone.utc)
            description = self._generate_cluster_description(list(tags), len(news_ids))
            tags_str = ", ".join(list(tags)[:10])
            
            # ✅ إضافة created_at و updated_at
            self.cursor.execute("""
                INSERT INTO news_clusters (description, tags, category_id, news_count, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (description, tags_str, category_id, len(news_ids), now, now))
            
            cluster_id = self.cursor.fetchone()[0]
            
            # ربط الأخبار
            for news_id in news_ids:
                self.cursor.execute("""
                    INSERT INTO news_cluster_members (cluster_id, news_id)
                    VALUES (%s, %s)
                """, (cluster_id, news_id))
            
            self.conn.commit()
            
            # تحديث cache
            self.existing_clusters[cluster_id] = {
                'tags': tags,
                'category_id': category_id,
                'news_ids': set(news_ids),
                'created_at': now,
                'updated_at': now
            }
            
            print(f"   📚 Cluster {cluster_id}: {len(news_ids)} news")
            return True
            
        except Exception as e:
            self.conn.rollback()
            print(f"   ❌ Error creating cluster: {e}")
            return False
    
    def _clean_old_clusters(self):
        """حذف clusters قديمة"""
        try:
            # حذف أعضاء المجموعات أولاً ثم المجموعات
            self.cursor.execute("DELETE FROM news_cluster_members")
            self.cursor.execute("DELETE FROM news_clusters")
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"   ❌ Error cleaning: {e}")
    
    def _parse_tags(self, tags_string: str) -> List[str]:
        """تحويل tags من string"""
        if not tags_string:
            return []
        return [tag.strip() for tag in tags_string.split(',') if tag.strip()]
    
    def _group_by_category(self, news_data: List[Dict]) -> Dict:
        """تجميع حسب category"""
        categories = defaultdict(list)
        for news in news_data:
            categories[news['category_id']].append(news)
        return dict(categories)
    
    def _calculate_tag_similarity(self, tags1: List[str], tags2: List[str]) -> float:
        """حساب التشابه بين lists"""
        if not tags1 or not tags2:
            return 0.0
        set1 = set(tags1)
        set2 = set(tags2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
    
    def _calculate_tag_similarity_sets(self, set1: set, set2: set) -> float:
        """حساب التشابه بين sets"""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
    
    def _generate_cluster_description(self, tags: List[str], news_count: int) -> str:
        """إنشاء وصف"""
        top_tags = tags[:5]
        if news_count == 1:
            return f"خبر منفرد: {', '.join(top_tags)}"
        else:
            return f"مجموعة أخبار: {', '.join(top_tags)} ({news_count} أخبار)"
    
    def close(self):
        """إغلاق الاتصال"""
        try:
            if hasattr(self, 'cursor') and self.cursor:
                self.cursor.close()
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
            print("✅ Database connection closed")
        except Exception as e:
            print(f"⚠️  Error closing: {e}")
    
    def __del__(self):
        """Destructor"""
        try:
            self.close()
        except:
            pass