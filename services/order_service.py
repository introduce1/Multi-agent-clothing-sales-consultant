"""
订单服务模块
提供订单创建、查询、状态更新和物流跟踪功能
"""

import sqlite3
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import random
import asyncio
from pathlib import Path

@dataclass
class OrderItem:
    """订单商品项"""
    product_id: str
    product_name: str
    price: float
    quantity: int
    image_url: str
    product_sku: str = ""
    product_category: str = ""
    specifications: Dict[str, str] = None

@dataclass
class ShippingAddress:
    """收货地址"""
    name: str
    phone: str
    province: str
    city: str
    district: str
    address: str
    postal_code: str = ""

@dataclass
class LogisticsInfo:
    """物流信息"""
    tracking_number: str
    company: str
    status: str
    current_location: str
    estimated_delivery: str
    tracking_history: List[Dict[str, Any]]
    origin_address: str = ""
    destination_address: str = ""
    route_nodes: List[Dict[str, Any]] = None

@dataclass
class Order:
    """订单信息"""
    order_id: str
    user_id: str
    items: List[OrderItem]
    total_amount: float
    shipping_fee: float
    discount_amount: float
    final_amount: float
    status: str  # pending, paid, shipped, delivered, cancelled
    payment_method: str
    shipping_address: ShippingAddress
    logistics_info: Optional[LogisticsInfo]
    created_at: str
    updated_at: str
    notes: str = ""

class OrderService:
    """订单服务类"""
    
    def __init__(self, db_path: str = "data/customer_service.db"):
        """初始化订单服务"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        
        # 模拟物流公司
        self.logistics_companies = [
            "顺丰速运", "圆通速递", "中通快递", "申通快递", 
            "韵达速递", "百世快递", "德邦快递", "京东物流"
        ]
        
        # 模拟城市列表
        self.cities = [
            "北京市", "上海市", "广州市", "深圳市", "杭州市",
            "南京市", "武汉市", "成都市", "西安市", "重庆市"
        ]
        
        # 物流状态模板
        self.logistics_templates = {
            "已下单": "您的订单已提交，商家正在准备发货",
            "已发货": "商品已从{origin}发出，正在运输途中",
            "运输中": "快件正在{location}处理中",
            "派送中": "快件已到达{destination}，正在派送",
            "已签收": "快件已在{destination}签收，感谢您的使用"
        }

    def _generate_11_digit_number(self) -> str:
        """生成11位纯数字订单号"""
        return str(random.randint(10_000_000_000, 99_999_999_999))

    def _init_database(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    items TEXT NOT NULL,
                    total_amount REAL NOT NULL,
                    shipping_fee REAL NOT NULL,
                    discount_amount REAL NOT NULL,
                    final_amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    payment_method TEXT NOT NULL,
                    shipping_address TEXT NOT NULL,
                    logistics_info TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    notes TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS logistics_tracking (
                    tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    tracking_number TEXT NOT NULL,
                    company TEXT NOT NULL,
                    status TEXT NOT NULL,
                    location TEXT NOT NULL,
                    description TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders (order_id)
                )
            """)

    def create_order(self, user_id: str, items: List[Dict], 
                    shipping_address: Dict, payment_method: str = "支付宝",
                    notes: str = "") -> Order:
        """创建订单"""
        order_id = f"TB{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
        
        # 转换商品项
        order_items = []
        total_amount = 0
        for item in items:
            order_item = OrderItem(
                product_id=item["product_id"],
                product_name=item["product_name"],
                product_sku=item.get("product_sku", f"SKU{random.randint(100000,999999)}"),
                product_category=item.get("product_category", random.choice(["上衣","裤装","鞋靴","裙装","外套"])),
                price=item["price"],
                quantity=item.get("quantity", 1),
                image_url=item.get("image_url", ""),
                specifications=item.get("specifications", {})
            )
            order_items.append(order_item)
            total_amount += order_item.price * order_item.quantity
        
        # 计算费用
        shipping_fee = 0 if total_amount >= 88 else 10  # 满88包邮
        discount_amount = 0
        final_amount = total_amount + shipping_fee - discount_amount
        
        # 创建收货地址
        addr = ShippingAddress(**shipping_address)
        
        # 创建订单
        order = Order(
            order_id=order_id,
            user_id=user_id,
            items=order_items,
            total_amount=total_amount,
            shipping_fee=shipping_fee,
            discount_amount=discount_amount,
            final_amount=final_amount,
            status="pending",
            payment_method=payment_method,
            shipping_address=addr,
            logistics_info=None,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            notes=notes
        )
        
        # 保存到数据库
        self._save_order(order)
        return order

    def _save_order(self, order: Order):
        """保存订单到数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO orders 
                (order_id, user_id, items, total_amount, shipping_fee, 
                 discount_amount, final_amount, status, payment_method, 
                 shipping_address, logistics_info, created_at, updated_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order.order_id,
                order.user_id,
                json.dumps([asdict(item) for item in order.items], ensure_ascii=False),
                order.total_amount,
                order.shipping_fee,
                order.discount_amount,
                order.final_amount,
                order.status,
                order.payment_method,
                json.dumps(asdict(order.shipping_address), ensure_ascii=False),
                json.dumps(asdict(order.logistics_info), ensure_ascii=False) if order.logistics_info else None,
                order.created_at,
                order.updated_at,
                order.notes
            ))

    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM orders WHERE order_id = ?
            """, (order_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            # 解析数据
            items_data = json.loads(row[2])
            items = [OrderItem(**item) for item in items_data]
            
            shipping_address = ShippingAddress(**json.loads(row[9]))
            
            logistics_info = None
            if row[10]:
                logistics_data = json.loads(row[10])
                logistics_info = LogisticsInfo(**logistics_data)
            
            return Order(
                order_id=row[0],
                user_id=row[1],
                items=items,
                total_amount=row[3],
                shipping_fee=row[4],
                discount_amount=row[5],
                final_amount=row[6],
                status=row[7],
                payment_method=row[8],
                shipping_address=shipping_address,
                logistics_info=logistics_info,
                created_at=row[11],
                updated_at=row[12],
                notes=row[13] or ""
            )

    def update_order_status(self, order_id: str, status: str) -> bool:
        """更新订单状态"""
        order = self.get_order(order_id)
        if not order:
            return False
        
        order.status = status
        order.updated_at = datetime.now().isoformat()
        
        # 如果状态变为已支付，创建物流信息
        if status == "paid" and not order.logistics_info:
            self._create_logistics_info(order)
        
        # 如果状态变为已发货，开始物流跟踪
        elif status == "shipped":
            self._start_logistics_tracking(order)
        
        self._save_order(order)
        return True

    def _create_logistics_info(self, order: Order):
        """创建物流信息"""
        tracking_number = f"{random.choice(['SF', 'YT', 'ZT', 'ST'])}{random.randint(100000000000, 999999999999)}"
        company = random.choice(self.logistics_companies)
        origin_city = random.choice(self.cities)
        origin_hub = f"{origin_city}{random.choice(['转运中心','分拨中心','物流园区'])}"
        destination_hub = f"{order.shipping_address.city}{order.shipping_address.district}"
        
        logistics_info = LogisticsInfo(
            tracking_number=tracking_number,
            company=company,
            status="已下单",
            current_location="商家仓库",
            estimated_delivery=(datetime.now() + timedelta(days=random.randint(2, 5))).strftime("%Y-%m-%d"),
            tracking_history=[{
                "status": "已下单",
                "location": "商家仓库",
                "description": self.logistics_templates["已下单"],
                "timestamp": datetime.now().isoformat()
            }],
            origin_address=origin_hub,
            destination_address=destination_hub,
            route_nodes=[{"node": origin_hub, "arrived_at": datetime.now().isoformat()}]
        )
        
        order.logistics_info = logistics_info

    def _start_logistics_tracking(self, order: Order):
        """开始物流跟踪"""
        if not order.logistics_info:
            return
        
        # 添加发货记录
        origin_city = random.choice(self.cities)
        order.logistics_info.status = "已发货"
        order.logistics_info.current_location = origin_city
        
        tracking_record = {
            "status": "已发货",
            "location": origin_city,
            "description": self.logistics_templates["已发货"].format(origin=origin_city),
            "timestamp": datetime.now().isoformat()
        }

        order.logistics_info.tracking_history.append(tracking_record)
        # 路由节点补充
        try:
            if order.logistics_info.route_nodes is None:
                order.logistics_info.route_nodes = []
            order.logistics_info.route_nodes.append({"node": origin_city, "arrived_at": tracking_record["timestamp"]})
        except Exception:
            pass
        
        # 保存物流跟踪记录
        self._save_logistics_tracking(order.order_id, order.logistics_info.tracking_number,
                                    order.logistics_info.company, tracking_record)

    def _save_logistics_tracking(self, order_id: str, tracking_number: str, 
                               company: str, record: Dict):
        """保存物流跟踪记录"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO logistics_tracking 
                (order_id, tracking_number, company, status, location, description, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id,
                tracking_number,
                company,
                record["status"],
                record["location"],
                record["description"],
                record["timestamp"]
            ))

    def seed_mock_orders(self, count: int = 30) -> List[Dict[str, Any]]:
        """生成并写入模拟订单到数据库，同时保存到txt文件

        - 订单号为11位纯数字
        - 每个订单包含随机物流状态与轨迹
        - 在 data/mock_orders.txt 输出便于测试
        """
        statuses = ["已下单", "已发货", "运输中", "派送中", "已签收"]
        generated = []

        for _ in range(count):
            order_number = self._generate_11_digit_number()

            # 随机商品
            item = OrderItem(
                product_id=str(uuid.uuid4())[:8],
                product_name=random.choice(["时尚休闲T恤", "牛仔裤", "运动鞋", "连衣裙", "羽绒服"]),
                product_sku=f"SKU{random.randint(100000,999999)}",
                product_category=random.choice(["上衣","裤装","鞋靴","裙装","外套"]),
                price=float(random.choice([99, 199, 299, 399, 599, 899])),
                quantity=random.randint(1, 3),
                image_url="",
                specifications={"颜色": random.choice(["白色", "黑色", "蓝色", "粉色"]), "尺码": random.choice(["S","M","L","XL"])}
            )

            total = item.price * item.quantity
            shipping_fee = 0 if total >= 88 else 10

            addr = ShippingAddress(
                name=random.choice(["张三", "李四", "王五", "赵六"]),
                phone=f"1{random.randint(3000000000, 9999999999)}",
                province="北京市",
                city=random.choice(["北京市", "上海市", "广州市", "深圳市", "杭州市"]),
                district=random.choice(["朝阳区", "海淀区", "浦东新区", "天河区", "南山区"]),
                address="XX路XX号XX小区",
                postal_code="100000"
            )

            # 初始物流信息
            company = random.choice(self.logistics_companies)
            tracking_number = f"{random.choice(['SF','YT','ZT','ST'])}{random.randint(100000000000, 999999999999)}"
            init_status = random.choice(statuses)
            origin_city = random.choice(self.cities)
            origin_hub = f"{origin_city}{random.choice(['转运中心','分拨中心','物流园区'])}"
            destination_hub = f"{addr.city}{addr.district}"

            history = [{
                "status": "已下单",
                "location": "商家仓库",
                "description": self.logistics_templates["已下单"],
                "timestamp": datetime.now().isoformat()
            }]

            # 如果随机状态在后续环节，补齐必要轨迹
            if init_status in ["已发货", "运输中", "派送中", "已签收"]:
                record = {
                    "status": "已发货",
                    "location": origin_city,
                    "description": self.logistics_templates["已发货"].format(origin=origin_city),
                    "timestamp": datetime.now().isoformat()
                }
                history.append(record)
                if init_status in ["运输中", "派送中", "已签收"]:
                    loc = random.choice(self.cities)
                    record2 = {
                        "status": "运输中",
                        "location": loc,
                        "description": self.logistics_templates["运输中"].format(location=loc),
                        "timestamp": datetime.now().isoformat()
                    }
                    history.append(record2)
                    if init_status in ["派送中", "已签收"]:
                        dest = f"{addr.city}{addr.district}"
                        record3 = {
                            "status": "派送中",
                            "location": dest,
                            "description": self.logistics_templates["派送中"].format(destination=dest),
                            "timestamp": datetime.now().isoformat()
                        }
                        history.append(record3)
                        if init_status == "已签收":
                            record4 = {
                                "status": "已签收",
                                "location": addr.address,
                                "description": self.logistics_templates["已签收"].format(destination=addr.address),
                                "timestamp": datetime.now().isoformat()
                            }
                            history.append(record4)

            # 路由节点（按轨迹生成）
            route_nodes = [{"node": origin_hub, "arrived_at": history[0]["timestamp"]}]
            for rec in history[1:]:
                route_nodes.append({"node": rec["location"], "arrived_at": rec["timestamp"]})

            logistics = LogisticsInfo(
                tracking_number=tracking_number,
                company=company,
                status=init_status,
                current_location=origin_city if init_status != "已签收" else addr.address,
                estimated_delivery=(datetime.now() + timedelta(days=random.randint(1, 5))).strftime("%Y-%m-%d"),
                tracking_history=history,
                origin_address=origin_hub,
                destination_address=destination_hub,
                route_nodes=route_nodes
            )

            order = Order(
                order_id=order_number,  # 使用11位纯数字作为订单号
                user_id=str(uuid.uuid4())[:8],
                items=[item],
                total_amount=total,
                shipping_fee=shipping_fee,
                discount_amount=0.0,
                final_amount=total + shipping_fee,
                status="delivered" if init_status == "已签收" else ("shipped" if init_status in ["已发货", "运输中", "派送中"] else "paid"),
                payment_method="支付宝",
                shipping_address=addr,
                logistics_info=logistics,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                notes="模拟订单"
            )

            self._save_order(order)

            # 保存每条物流轨迹到表
            for rec in history:
                self._save_logistics_tracking(order.order_id, tracking_number, company, rec)

            generated.append({
                "order_number": order_number,
                "status": init_status,
                "company": company,
                "tracking_number": tracking_number,
                "product_name": item.product_name,
                "product_sku": item.product_sku,
                "product_category": item.product_category,
                "quantity": item.quantity,
                "unit_price": item.price,
                "origin": origin_hub,
                "destination": destination_hub,
                "current_location": logistics.current_location
            })

        # 写入txt文件
        txt_path = self.db_path.parent / "mock_orders.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            # 订单号	状态	承运商	运单号	商品	SKU	类目	数量	单价	发货地	收货地	当前所在
            for g in generated:
                f.write(
                    f"{g['order_number']}\t{g['status']}\t{g['company']}\t{g['tracking_number']}\t"
                    f"{g['product_name']}\t{g['product_sku']}\t{g['product_category']}\t{g['quantity']}\t{g['unit_price']}\t"
                    f"{g['origin']}\t{g['destination']}\t{g['current_location']}\n"
                )

        return generated

    async def get_order_by_number(self, order_number: str) -> Dict[str, Any]:
        """按订单号查询并返回Agent友好结构"""
        order = self.get_order(order_number)
        if not order:
            return {"success": False, "orders": []}

        # 构造响应
        item = order.items[0] if order.items else None
        info = {
            "order_number": order.order_id,
            "status": order.logistics_info.status if order.logistics_info else order.status,
            "product_name": item.product_name if item else "",
            "amount": order.final_amount,
            "create_time": order.created_at,
            "logistics_info": None,
            "phone": order.shipping_address.phone,
            "delivery_address": order.shipping_address.address,
            "estimated_delivery": order.logistics_info.estimated_delivery if order.logistics_info else None,
            "product": {
                "name": item.product_name if item else "",
                "sku": item.product_sku if item else "",
                "category": item.product_category if item else "",
                "quantity": item.quantity if item else 0,
                "unit_price": item.price if item else 0.0,
                "specifications": item.specifications if item else {}
            },
            "addresses": {
                "origin": (order.logistics_info.origin_address if order.logistics_info else ""),
                "destination": f"{order.shipping_address.city}{order.shipping_address.district} {order.shipping_address.address}",
                "recipient": order.shipping_address.name,
                "phone": order.shipping_address.phone
            }
        }
        if order.logistics_info:
            # 合并轨迹为简单文本
            last = order.logistics_info.tracking_history[-1] if order.logistics_info.tracking_history else None
            info["logistics_info"] = {
                "tracking_number": order.logistics_info.tracking_number,
                "company": order.logistics_info.company,
                "current_status": order.logistics_info.status,
                "current_location": order.logistics_info.current_location,
                "last_update": last["timestamp"] if last else order.updated_at,
                "history": order.logistics_info.tracking_history,
                "origin": order.logistics_info.origin_address,
                "destination": order.logistics_info.destination_address,
                "route_nodes": order.logistics_info.route_nodes or []
            }

        return {"success": True, "orders": [info]}

    async def get_orders_by_phone(self, phone: str, limit: int = 5) -> Dict[str, Any]:
        """按收件手机号查询订单（地址JSON里包含phone）"""
        results: List[Dict[str, Any]] = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM orders")
            for row in cursor.fetchall():
                addr = json.loads(row[9])
                if addr.get("phone") == phone:
                    # 复用 get_order_by_number 的结构
                    order_id = row[0]
                    data = await self.get_order_by_number(order_id)
                    if data.get("orders"):
                        results.extend(data["orders"])
                    if len(results) >= limit:
                        break
        return {"success": True, "orders": results}


    def simulate_logistics_progress(self, order_id: str) -> bool:
        """模拟物流进度更新"""
        order = self.get_order(order_id)
        if not order or not order.logistics_info:
            return False
        
        current_status = order.logistics_info.status
        
        # 定义状态流转
        status_flow = ["已下单", "已发货", "运输中", "派送中", "已签收"]
        
        try:
            current_index = status_flow.index(current_status)
            if current_index < len(status_flow) - 1:
                next_status = status_flow[current_index + 1]
                
                # 生成新的物流记录
                location = random.choice(self.cities)
                if next_status == "派送中":
                    location = f"{order.shipping_address.city}{order.shipping_address.district}"
                elif next_status == "已签收":
                    location = order.shipping_address.address
                
                description = self.logistics_templates[next_status]
                if "{location}" in description:
                    description = description.format(location=location)
                elif "{destination}" in description:
                    description = description.format(destination=location)
                
                tracking_record = {
                    "status": next_status,
                    "location": location,
                    "description": description,
                    "timestamp": datetime.now().isoformat()
                }
                
                # 更新物流信息
                order.logistics_info.status = next_status
                order.logistics_info.current_location = location
                order.logistics_info.tracking_history.append(tracking_record)
                try:
                    if order.logistics_info.route_nodes is None:
                        order.logistics_info.route_nodes = []
                    order.logistics_info.route_nodes.append({"node": location, "arrived_at": tracking_record["timestamp"]})
                except Exception:
                    pass
                
                # 如果已签收，更新订单状态
                if next_status == "已签收":
                    order.status = "delivered"
                
                order.updated_at = datetime.now().isoformat()
                
                # 保存更新
                self._save_order(order)
                self._save_logistics_tracking(order_id, order.logistics_info.tracking_number,
                                            order.logistics_info.company, tracking_record)
                
                return True
        except ValueError:
            pass
        
        return False

    def get_user_orders(self, user_id: str, limit: int = 10) -> List[Order]:
        """获取用户订单列表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM orders WHERE user_id = ? 
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, limit))
            
            orders = []
            for row in cursor.fetchall():
                items_data = json.loads(row[2])
                items = [OrderItem(**item) for item in items_data]
                
                shipping_address = ShippingAddress(**json.loads(row[9]))
                
                logistics_info = None
                if row[10]:
                    logistics_data = json.loads(row[10])
                    logistics_info = LogisticsInfo(**logistics_data)
                
                order = Order(
                    order_id=row[0],
                    user_id=row[1],
                    items=items,
                    total_amount=row[3],
                    shipping_fee=row[4],
                    discount_amount=row[5],
                    final_amount=row[6],
                    status=row[7],
                    payment_method=row[8],
                    shipping_address=shipping_address,
                    logistics_info=logistics_info,
                    created_at=row[11],
                    updated_at=row[12],
                    notes=row[13] or ""
                )
                orders.append(order)
            
            return orders

    def cancel_order(self, order_id: str, reason: str = "") -> bool:
        """取消订单"""
        order = self.get_order(order_id)
        if not order:
            return False
        
        # 只有待支付和已支付的订单可以取消
        if order.status not in ["pending", "paid"]:
            return False
        
        order.status = "cancelled"
        order.notes = f"取消原因: {reason}" if reason else "用户取消"
        order.updated_at = datetime.now().isoformat()
        
        self._save_order(order)
        return True

    def get_order_statistics(self, user_id: str = None) -> Dict[str, Any]:
        """获取订单统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            if user_id:
                cursor = conn.execute("""
                    SELECT status, COUNT(*), SUM(final_amount) 
                    FROM orders WHERE user_id = ? 
                    GROUP BY status
                """, (user_id,))
            else:
                cursor = conn.execute("""
                    SELECT status, COUNT(*), SUM(final_amount) 
                    FROM orders 
                    GROUP BY status
                """)
            
            stats = {}
            total_orders = 0
            total_amount = 0
            
            for row in cursor.fetchall():
                status, count, amount = row
                stats[status] = {
                    "count": count,
                    "amount": amount or 0
                }
                total_orders += count
                total_amount += amount or 0
            
            return {
                "total_orders": total_orders,
                "total_amount": total_amount,
                "by_status": stats
            }

# 导出一个全局实例，便于在智能体与API中复用
order_service = OrderService(db_path="data/mock_orders.db")

__all__ = ["OrderService", "order_service"]