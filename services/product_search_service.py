# -*- coding: utf-8 -*-
"""
商品搜索服务 - 集成全网商品搜索API
"""

import requests
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

class ProductSearchService:
    """全网商品搜索服务"""
    
    def __init__(self):
        self.appkey = ""
        self.sid = ""
        self.pid = ""
        self.base_url = ""
    
    async def search_products(self, 
                            keyword: str, 
                            page: int = 1, 
                            page_size: int = 10, 
                            sort: str = 'total_sales_des',
                            price_min: Optional[float] = None,
                            price_max: Optional[float] = None) -> Dict[str, Any]:
        """
        搜索商品 - 支持模糊搜索和关键词扩展
        
        Args:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量
            sort: 排序方式 (total_sales_des, price_asc, price_desc等)
            price_min: 最低价格
            price_max: 最高价格
            
        Returns:
            搜索结果字典
        """
        # 尝试多种搜索策略
        search_strategies = [
            keyword,  # 原始关键词
            self._expand_keyword(keyword),  # 扩展关键词
            self._simplify_keyword(keyword),  # 简化关键词
        ]
        
        for strategy_keyword in search_strategies:
            if not strategy_keyword:
                continue
                
            params = {
                'appkey': self.appkey,
                'sid': self.sid,
                'pid': self.pid,
                'q': strategy_keyword,
                'page': page,
                'page_size': page_size,
                'sort': sort
            }
            
            # 添加API原生价格过滤支持
            if price_min is not None:
                params['price_min'] = price_min
            if price_max is not None:
                params['price_max'] = price_max
            
            try:
                logger.info(f"尝试搜索关键词: {strategy_keyword}")
                logger.info(f"请求参数: {params}")
                
                # 添加重试机制和更详细的超时处理
                max_retries = 2
                for attempt in range(max_retries + 1):
                    try:
                        response = requests.get(self.base_url, params=params, timeout=8)
                        logger.info(f"API响应状态码: {response.status_code}")
                        
                        # 检查HTTP状态码
                        if response.status_code != 200:
                            logger.warning(f"API返回非200状态码: {response.status_code}, 尝试: {attempt + 1}/{max_retries + 1}")
                            if attempt < max_retries:
                                continue
                            else:
                                raise Exception(f"API返回状态码: {response.status_code}")
                        
                        result = response.json()
                        logger.info(f"API响应内容: {result}")
                        
                        if result.get('status') == 200:
                            items = result.get('content', [])
                            
                            # 如果找到商品，处理并返回
                            if items:
                                # 价格过滤
                                if price_min is not None or price_max is not None:
                                    items = self._filter_by_price(items, price_min, price_max)
                                
                                # 性别过滤（根据关键词中的性别意图）
                                target_gender = self._detect_gender_from_keyword(strategy_keyword)
                                if target_gender:
                                    before_count = len(items)
                                    items = self._filter_by_gender(items, target_gender)
                                    logger.info(f"性别过滤({target_gender})：{before_count} -> {len(items)}")
                                
                                # 格式化商品信息
                                formatted_items = [self._format_product_info(item) for item in items]
                                
                                return {
                                    'success': True,
                                    'count': len(formatted_items),
                                    'items': formatted_items,
                                    'message': f'找到 {len(formatted_items)} 个相关商品',
                                    'search_keyword': strategy_keyword
                                }
                        
                        # 如果是301状态（无结果），继续尝试下一个策略
                        elif result.get('status') == 301:
                            logger.info(f"关键词 '{strategy_keyword}' 无搜索结果，尝试下一个策略")
                            break  # 跳出重试循环，继续下一个搜索策略
                            
                    except requests.exceptions.Timeout:
                        logger.warning(f"搜索关键词 '{strategy_keyword}' 超时, 尝试: {attempt + 1}/{max_retries + 1}")
                        if attempt < max_retries:
                            continue
                        else:
                            raise Exception("API请求超时")
                    except requests.exceptions.ConnectionError:
                        logger.warning(f"搜索关键词 '{strategy_keyword}' 连接错误, 尝试: {attempt + 1}/{max_retries + 1}")
                        if attempt < max_retries:
                            continue
                        else:
                            raise Exception("API连接错误")
                    except requests.exceptions.RequestException as e:
                        logger.warning(f"搜索关键词 '{strategy_keyword}' 请求异常: {str(e)}, 尝试: {attempt + 1}/{max_retries + 1}")
                        if attempt < max_retries:
                            continue
                        else:
                            raise
                    
            except Exception as e:
                logger.error(f"搜索关键词 '{strategy_keyword}' 时出现异常: {str(e)}")
                continue
        
        # 所有策略都失败，返回友好的无结果响应
        logger.info(f"所有搜索策略都无结果，原始关键词: {keyword}")
        return {
            'success': True,  # 仍然标记为成功，避免报错
            'count': 0,
            'items': [],
            'message': f'暂时没有找到与"{keyword}"相关的商品，建议尝试其他关键词',
            'search_keyword': keyword
        }
    
    def _expand_keyword(self, keyword: str) -> str:
        """
        扩展关键词 - 添加相关词汇提高搜索成功率
        """
        if not keyword:
            return ""
            
        # 常见的关键词扩展映射
        expansion_map = {
            '衬衫': '衬衫 衬衣 shirt',
            '裤子': '裤子 长裤 pants',
            '裙子': '裙子 连衣裙 dress skirt',
            '外套': '外套 夹克 jacket coat',
            '鞋子': '鞋子 鞋 shoes',
            '包': '包 包包 bag',
            '帽子': '帽子 hat cap',
            '手表': '手表 腕表 watch',
            '眼镜': '眼镜 glasses',
            '项链': '项链 necklace',
            '耳环': '耳环 earrings',
            '戒指': '戒指 ring',
            '手链': '手链 bracelet',
            '围巾': '围巾 scarf',
            '手套': '手套 gloves',
            '袜子': '袜子 socks',
            '内衣': '内衣 underwear',
            '睡衣': '睡衣 pajamas',
            '运动服': '运动服 sportswear',
            '牛仔裤': '牛仔裤 jeans',
            'T恤': 'T恤 t-shirt tshirt',
            '毛衣': '毛衣 sweater',
            '西装': '西装 suit',
            '连衣裙': '连衣裙 dress',
            '短裤': '短裤 shorts',
            '背心': '背心 vest',
            '风衣': '风衣 trench coat',
            '羽绒服': '羽绒服 down jacket',
            '卫衣': '卫衣 hoodie',
            'polo衫': 'polo衫 polo shirt',
            '马甲': '马甲 vest waistcoat',
        }
        
        # 颜色扩展
        color_expansion = {
            '红': '红色 red',
            '蓝': '蓝色 blue',
            '绿': '绿色 green',
            '黄': '黄色 yellow',
            '黑': '黑色 black',
            '白': '白色 white',
            '灰': '灰色 gray grey',
            '粉': '粉色 pink',
            '紫': '紫色 purple',
            '橙': '橙色 orange',
            '棕': '棕色 brown',
            '米': '米色 beige',
            '卡其': '卡其色 khaki',
            '藏青': '藏青色 navy',
        }
        
        # 尺码扩展
        size_expansion = {
            'xs': 'XS 加小号',
            's': 'S 小号',
            'm': 'M 中号',
            'l': 'L 大号',
            'xl': 'XL 加大号',
            'xxl': 'XXL 特大号',
            'xxxl': 'XXXL 超大号',
        }
        
        expanded = keyword.lower()
        
        # 应用扩展映射
        for original, expanded_terms in {**expansion_map, **color_expansion, **size_expansion}.items():
            if original in expanded:
                expanded = expanded.replace(original, expanded_terms)
        
        return expanded.strip()
    
    def _simplify_keyword(self, keyword: str) -> str:
        """
        简化关键词 - 提取核心词汇
        """
        if not keyword:
            return ""
            
        # 移除常见的修饰词
        remove_words = ['的', '了', '吧', '呢', '啊', '哦', '嗯', '好', '很', '非常', '特别', '比较', '有点', '一点', '一些']
        
        simplified = keyword
        for word in remove_words:
            simplified = simplified.replace(word, '')
        
        # 提取核心服装类别词
        core_categories = ['衬衫', '裤子', '裙子', '外套', '鞋子', '包', '帽子', '手表', '眼镜', 
                          '项链', '耳环', '戒指', '手链', '围巾', '手套', '袜子', '内衣', '睡衣',
                          '运动服', '牛仔裤', 'T恤', '毛衣', '西装', '连衣裙', '短裤', '背心',
                          '风衣', '羽绒服', '卫衣', 'polo衫', '马甲']
        
        for category in core_categories:
            if category in simplified:
                return category
        
        # 如果没有找到核心类别，返回清理后的关键词
        return simplified.strip()

    def _filter_by_price(self, items: List[Dict], price_min: Optional[float], price_max: Optional[float]) -> List[Dict]:
        """根据价格过滤商品"""
        filtered_items = []
        
        for item in items:
            try:
                price = float(item.get('quanhou_jiage', 0))
                
                if price_min is not None and price < price_min:
                    continue
                if price_max is not None and price > price_max:
                    continue
                    
                filtered_items.append(item)
            except (ValueError, TypeError):
                # 价格无法转换时跳过
                continue
                
        return filtered_items

    def _detect_gender_from_keyword(self, keyword: str) -> Optional[str]:
        """从关键词中检测性别意图：返回 'male'、'female' 或 None。"""
        if not keyword:
            return None
        k = (keyword or '').lower()
        male_markers = ['男士', '男生', '男性', '男装', '男款', '男']
        female_markers = ['女士', '女生', '女性', '女装', '女款', '女']
        has_m = any(m in k for m in male_markers)
        has_f = any(f in k for f in female_markers)
        if has_m and not has_f:
            return 'male'
        if has_f and not has_m:
            return 'female'
        return None

    def _filter_by_gender(self, items: List[Dict], target_gender: str) -> List[Dict]:
        """根据目标性别过滤商品。保留中性/男女同款。"""
        if not target_gender:
            return items
        unisex_markers = ['中性', '男女同款', '情侣', '通用', 'unisex', '男女']
        female_markers = ['女士', '女生', '女性', '女装', '女款', '女']
        male_markers = ['男士', '男生', '男性', '男装', '男款', '男']

        filtered = []
        for item in items:
            text_parts = [
                str(item.get('tao_title', '')),
                str(item.get('title', '')),
                str(item.get('category_name', '')),
                str(item.get('shop_title', '')),
                str(item.get('nick', '')),
                str(item.get('jianjie', '')),
            ]
            t = ' '.join(text_parts).lower()
            is_unisex = any(u.lower() in t for u in unisex_markers)
            if is_unisex:
                filtered.append(item)
                continue
            if target_gender == 'male':
                if any(f.lower() in t for f in female_markers):
                    continue
                filtered.append(item)
            elif target_gender == 'female':
                if any(m.lower() in t for m in male_markers):
                    continue
                filtered.append(item)
        return filtered
    
    def _format_product_info(self, item: Dict) -> Dict[str, Any]:
        """
        格式化商品信息，返回指定字段
        """
        # 提取价格信息（优先取原价字段，若无则兼容其它字段）
        price = item.get("price") or item.get("size") or ""
        if price:
            try:
                price = float(price)
            except:
                price = ""
        
        # 提取品牌信息
        brand = item.get("pinpai_name", "")
        if not brand:
            # 从店铺名称中提取品牌
            shop_name = item.get("nick", "")
            if "旗舰店" in shop_name:
                brand = shop_name.replace("旗舰店", "").replace("官方", "").strip()
        
        return {
            # 基础商品信息
            "title": item.get("tao_title", item.get("title", "")),
            "price": price,
            "brand": brand,
            "shop_name": item.get("nick", ""),
            "jianjie": item.get("jianjie", ""),
            "size": item.get("size", ""),
            "quanhou_jiage": item.get("quanhou_jiage", ""),
            "coupon_info_money": item.get("coupon_info_money", ""),
            "coupon_info": item.get("coupon_info", ""),
            
            # 店铺信息
            "user_type": item.get("user_type", ""),
            "seller_id": item.get("seller_id", ""),
            "shop_dsr": item.get("shop_dsr", ""),
            "nick": item.get("nick", ""),
            "shop_title": item.get("shop_title", ""),
            "provcity": item.get("provcity", ""),
            
            # 销售数据
            "volume": item.get("volume", ""),
            "sellCount": item.get("sellCount", ""),
            "commentCount": item.get("commentCount", ""),
            "favcount": item.get("favcount", ""),
            
            # 商品链接
            "item_url": item.get("item_url", ""),
            # 为避免联盟链接失效，提供基于标题的稳定搜索链接
            "search_url": (
                f"https://s.taobao.com/search?q={quote_plus(item.get('tao_title', item.get('title', '')))}"
                if item.get('tao_title') or item.get('title') else ""
            ),
            
            # 额外有用信息
            "tao_id": item.get("tao_id", ""),
            "pict_url": item.get("pict_url", ""),
            "tkrate3": item.get("tkrate3", ""),
            "category_name": item.get("category_name", "")
        }
    
    def build_search_keyword(self, requirements: Dict[str, Any]) -> str:
        """
        根据用户需求构建搜索关键词
        
        Args:
            requirements: 用户需求字典，包含gender, clothing_type等字段
            
        Returns:
            构建的搜索关键词
        """
        keywords = []
        
        # 添加性别信息
        gender = requirements.get("gender", "")
        if gender:
            keywords.append(gender)
        
        # 优先使用原始消息中的具体商品词汇
        original_keyword = requirements.get("search_keyword", "")
        specific_items = []
        
        # 检查原始关键词中的具体商品类型
        item_patterns = {
            "t恤": ["t恤", "T恤", "tshirt", "t-shirt"],
            "外套": ["外套", "夹克", "jacket"],
            "连衣裙": ["连衣裙", "裙子"],
            "衬衫": ["衬衫", "shirt"],
            "毛衣": ["毛衣", "sweater"],
            "牛仔裤": ["牛仔裤", "jeans"],
            "运动鞋": ["运动鞋", "sneaker"],
            "皮鞋": ["皮鞋", "leather shoes"]
        }
        
        # 从原始关键词中提取具体商品类型
        for item_type, patterns in item_patterns.items():
            if any(pattern in original_keyword.lower() for pattern in patterns):
                specific_items.append(item_type)
        
        # 如果找到具体商品类型，使用它们
        if specific_items:
            keywords.extend(specific_items)
        else:
            # 否则使用分类的服装类型
            clothing_type = requirements.get("clothing_type", "")
            if clothing_type and clothing_type != "服装":
                keywords.append(clothing_type)
        
        # 添加品牌偏好
        brand = requirements.get("brand_preference", "")
        if brand and brand != "无偏好":
            keywords.append(brand)
        
        # 添加风格偏好
        style = requirements.get("style_preference", "")
        if style:
            keywords.append(style)
        
        # 如果没有提取到关键信息，使用原始搜索关键词的前几个字
        if not keywords:
            if original_keyword:
                # 取前10个字符作为关键词
                keywords.append(original_keyword[:10])
        
        # 构建最终关键词
        final_keyword = " ".join(keywords) if keywords else "商品"
        
        return final_keyword
    
    def format_product_display(self, products: List[Dict], requirements: Dict[str, Any] = None) -> str:
        """
        格式化商品展示信息
        """
        if not products:
            return "抱歉，没有找到符合条件的商品。"
        
        # 根据需求生成个性化的开头
        search_keyword = requirements.get("search_keyword", "商品") if requirements else "商品"
        price_range = requirements.get("price_range", "") if requirements else ""
        
        display_text = f"为您找到 {len(products)} 款{search_keyword}"
        if price_range and price_range != "不限":
            display_text += f"（预算{price_range}）"
        display_text += "：\n\n"
        
        for i, product in enumerate(products[:5], 1):  # 最多显示5个商品
            display_text += f"🛍️ 商品 {i}\n"
            display_text += f"📝 商品名称: {product.get('title', '未知')}\n"
            
            if product.get('jianjie'):
                display_text += f"📋 商品简介: {product.get('jianjie')}\n"
            
            raw_price = product.get('price')
            raw_price_str = f"{raw_price:.2f}" if isinstance(raw_price, (int, float)) else (str(raw_price) if raw_price else '未知')
            display_text += f"💰 原价: ¥{raw_price_str}\n"
            display_text += f"💸 券后价: ¥{product.get('quanhou_jiage', '未知')}\n"
            
            if product.get('coupon_info_money'):
                display_text += f"🎫 优惠券: {product.get('coupon_info_money')}元券\n"
            
            if product.get('coupon_info'):
                display_text += f"🎟️ 优惠信息: {product.get('coupon_info')}\n"
            
            # 店铺信息
            shop_type = "天猫" if str(product.get('user_type')) == '1' else "淘宝"
            display_text += f"🏪 店铺: {product.get('nick', '未知店铺')} ({shop_type})\n"
            
            if product.get('shop_dsr'):
                display_text += f"⭐ 店铺评分: {product.get('shop_dsr')}\n"
            
            if product.get('provcity'):
                display_text += f"📍 发货地: {product.get('provcity')}\n"
            
            # 销售数据
            if product.get('volume'):
                display_text += f"📊 销量: {product.get('volume')} 件\n"
            
            if product.get('commentCount'):
                display_text += f"💬 评论数: {product.get('commentCount')}\n"
            
            if product.get('item_url'):
                display_text += f"🔗 商品链接: {product.get('item_url')}\n"
            
            display_text += "\n" + "="*50 + "\n\n"
        
        if len(products) > 5:
            display_text += f"还有 {len(products) - 5} 款商品，如需查看更多请告诉我！"
        
        return display_text

# 创建全局实例
product_search_service = ProductSearchService()