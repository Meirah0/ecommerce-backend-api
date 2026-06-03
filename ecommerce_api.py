import os
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from tinydb import TinyDB, Query
from tinydb.operations import set
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
db = TinyDB('ecommerce.json')

# Tables
products_table = db.table('products')
orders_table = db.table('orders')
cart_table = db.table('cart')

DEFAULT_PRODUCT_KEYS = {'id': "-", 'name': "-", 'price': 0.0, 'rating': "-", 'stock': 0, 'details': "-", 'category': "-"}
DEFAULT_ORDER_KEYS = {'id': "-", 'items': [], 'total': 0.0, 'order_number': "-"}
DEFAULT_CART_KEYS = {'id': "-", 'name': "-", 'price': 0.0, 'quantity': 1}
UPLOAD_FOLDER = 'images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}



def ensure_product_keys():
    """Ensure all products have the same keys with default values."""
    products = products_table.all()
    for product in products:
        for key in DEFAULT_PRODUCT_KEYS:
            if key not in product:
                products_table.update(set(key, DEFAULT_PRODUCT_KEYS[key]), doc_ids=[product.doc_id])


def ensure_order_keys():
    """Ensure all orders have the same keys with default values."""
    orders = orders_table.all()
    for order in orders:
        for key in DEFAULT_ORDER_KEYS:
            if key not in order:
                orders_table.update(set(key, DEFAULT_ORDER_KEYS[key]), doc_ids=[order.doc_id])


def ensure_cart_keys():
    """Ensure all cart items have the same keys with default values."""
    cart = cart_table.all()
    for item in cart:
        for key in DEFAULT_CART_KEYS:
            if key not in item:
                cart_table.update(set(key, DEFAULT_CART_KEYS[key]), doc_ids=[item.doc_id])

def allowed_file(filename):
    """Check if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



# Frontend
@app.route('/products', methods=['GET'])
def get_products():
    """Fetch all products. --> Main Page"""
    ensure_product_keys()
    products = products_table.all()
    return jsonify(products)


@app.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Fetch a single product by ID. --> Single Product Page"""
    ensure_product_keys()
    Product = Query()
    product = products_table.get(Product.id == product_id)
    if product:
        return jsonify(product)
    return jsonify({'error': 'Product not found'}), 404


@app.route('/products', methods=['POST'])
def add_product():
    """Add a new product with optional image upload. --> For Seller Page"""
    data = request.json if request.is_json else request.form.to_dict()
    
    # Handle default product keys
    for key in DEFAULT_PRODUCT_KEYS:
        if key not in data:
            data[key] = DEFAULT_PRODUCT_KEYS[key]
    
    # Generate unique product ID
    data['id'] = len(products_table) + 1
    
    # Handle image upload
    image_path = None
    if 'image' in request.files:
        image_file = request.files['image']
        
        # Validate file
        if image_file and allowed_file(image_file.filename):
            # Generate unique filename
            filename = f"{uuid.uuid4()}_{secure_filename(image_file.filename)}"
            
            # Ensure upload directory exists
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            
            # Save file
            full_path = os.path.join(UPLOAD_FOLDER, filename)
            image_file.save(full_path)
            
            # Store relative path in database
            image_path = f"/images/{filename}"
            data['image_path'] = image_path
    
    # Insert product data
    products_table.insert(data)
    ensure_product_keys()

    return jsonify({
        'message': 'Product added', 
        'id': data['id'],
        'image_path': image_path
    }), 201

# Error handling middleware
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large'}), 413


@app.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """Update a product. --> For Seller Page"""
    data = request.json
    Product = Query()
    updated = products_table.update(data, Product.id == product_id)
    if updated:
        ensure_product_keys()
        return jsonify({'message': 'Product updated'})
    return jsonify({'error': 'Product not found'}), 404


@app.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """Delete a product. --> For Seller Page"""
    Product = Query()
    deleted = products_table.remove(Product.id == product_id)
    if deleted:
        return jsonify({'message': 'Product deleted'})
    return jsonify({'error': 'Product not found'}), 404


# Cart
@app.route('/cart', methods=['GET'])
def get_cart():
    """Fetch all cart items. --> On cart icon"""
    ensure_cart_keys()
    cart = cart_table.all()
    return jsonify(cart)


@app.route('/cart', methods=['POST'])
def add_to_cart():
    """update stock.--> On Add to cart Button"""
    data = request.json
    Product = Query()
    product = products_table.get(Product.id == data.get('product_id'))

    if not product:
        return jsonify({'error': 'Product not found'}), 404
    if product['stock'] < data.get('quantity', 1):
        return jsonify({'error': 'Insufficient stock'}), 400

    # Create a cart item
    cart_item = {
        'id': len(cart_table) + 1,
        'name': product['name'],
        'price': product['price'],
        'quantity': data.get('quantity', 1),
    }
    cart_table.insert(cart_item)

    return jsonify({'message': 'Product added to cart and stock updated'}), 201


#------------------------------------------------------------------------------------------------------


@app.route('/cart/<int:cart_item_id>', methods=['PUT'])
def update_cart(cart_item_id):
    """Update the quantity of a cart item and adjust the product stock. --> Extra"""
    data = request.json

    # Validate input
    if 'quantity' not in data or data['quantity'] <= 0:
        return jsonify({'error': 'Invalid quantity'}), 400

    CartItem = Query()
    cart_item = cart_table.get(CartItem.id == cart_item_id)

    if not cart_item:
        return jsonify({'error': 'Cart item not found'}), 404

    # Retrieve the associated product
    Product = Query()
    product = products_table.get(Product.name == cart_item['name'])

    if not product:
        return jsonify({'error': 'Associated product not found'}), 404

    # Decrement stock
    new_stock = product['stock'] - data.get('quantity', 1)
    products_table.update(set('stock', new_stock), Product.id == product['id'])

    return jsonify({'message': 'Cart item updated and stock adjusted'})

#------------------------------------------------------------------------------------------------------


@app.route('/cart/<int:cart_item_id>', methods=['DELETE'])
def delete_from_cart(cart_item_id):
    """Remove a product from the cart and update stock.--> Extra"""
    CartItem = Query()
    cart_item = cart_table.get(CartItem.id == cart_item_id)

    if not cart_item:
        return jsonify({'error': 'Cart item not found'}), 404

    # Retrieve the associated product to restore stock
    Product = Query()
    product = products_table.get(Product.name == cart_item['name'])

    if product:
        # Restore stock
        new_stock = product['stock'] + cart_item['quantity']
        products_table.update(set('stock', new_stock), Product.id == product['id'])

    # Remove the cart item
    cart_table.remove(CartItem.id == cart_item_id)

    return jsonify({'message': 'Cart item removed and stock updated'})

#Orders

class OrderManager:
    def __init__(self, db):
        self.orders_table = db.table('orders')
        self.products_table = db.table('products')
        self.cart_table = db.table('cart')

    def validate_order_data(self, data):
        """Validate order data."""
        required_fields = ['customer_name', 'email', 'items']
        for field in required_fields:
            if not data.get(field):
                return False, f"Missing required field: {field}"
        return True, None

    def create_order(self, data):
        """Create a new order."""
        # Validate order data
        is_valid, error = self.validate_order_data(data)
        if not is_valid:
            return {'error': error}, 400

        # Calculate total price and validate stock
        total_price = 0
        validated_items = []

        for item in data['items']:
            Product = Query()
            product = self.products_table.get(Product.name == item['name'])
            
            if not product:
                return {'error': f"Product {item['name']} not found"}, 404
            
            if product['stock'] < item['quantity']:
                return {'error': f"Insufficient stock for {item['name']}"}, 400

            # Update product stock
            new_stock = product['stock'] - item['quantity']
            self.products_table.update(set('stock', new_stock), Product.name == item['name'])

            # Calculate item total
            item_total = product['price'] * item['quantity']
            total_price += item_total

            validated_items.append({
                'name': item['name'],
                'quantity': item['quantity'],
                'price': product['price']
            })

        # Create order
        order = {
            'id': str(uuid.uuid4()),
            'order_number': f'ORD-{datetime.now().strftime("%Y%m%d%H%M%S")}',
            'customer': {
                'name': data['customer_name'],
                'email': data['email'],
                'phone': data.get('phone', '')
            },
            'items': validated_items,
            'total_price': round(total_price, 2),
            'status': 'PENDING',
            'created_at': datetime.now().isoformat()
        }

        # Save order
        self.orders_table.insert(order)
        return order, 201

    def get_order(self, order_id):
        """Retrieve a specific order."""
        Order = Query()
        order = self.orders_table.get(Order.id == order_id)
        return order if order else None

    def get_all_orders(self):
        """Retrieve all orders."""
        return self.orders_table.all()

    def update_order_status(self, order_id, status):
        """Update order status."""
        Order = Query()
        updated = self.orders_table.update(
            set('status', status), 
            Order.id == order_id
        )
        return bool(updated)

    def delete_order(self, order_id):
        """Delete an order."""
        Order = Query()
        order = self.orders_table.get(Order.id == order_id)
        if not order:
            return False  # Order not found

        # Restore stock for each item in the order
        for item in order['items']:
            Product = Query()
            product = self.products_table.get(Product.name == item['name'])
            if product:
                # Add the quantity back to the product's stock
                new_stock = product['stock'] + item['quantity']
                self.products_table.update({'stock': new_stock}, Product.name == item['name'])

         # Remove the order
        deleted = self.orders_table.remove(Order.id == order_id)
        return bool(deleted)

# Orders
@app.route('/orders', methods=['POST'])
def create_order():
    """Adding Orders -> Checkout button"""
    data = request.json
    order_manager = OrderManager(db)
    order, status = order_manager.create_order(data)
    return jsonify(order), status

#------------------------------------------------------------------------------------------------------

@app.route('/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    """Getting Orders by id -> Done by Shopkeeper"""
    order_manager = OrderManager(db)
    order = order_manager.get_order(order_id)
    return jsonify(order) if order else (jsonify({'error': 'Order not found'}), 404)

@app.route('/orders', methods=['GET'])
def list_orders():
    """Getting all Orders -> Done by Shopkeeper"""
    order_manager = OrderManager(db)
    orders = order_manager.get_all_orders()
    return jsonify(orders)

@app.route('/orders/<order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    """Order -> Extra"""
    data = request.json
    order_manager = OrderManager(db)
    success = order_manager.update_order_status(order_id, data.get('status'))
    return jsonify({'updated order': success})

@app.route('/orders/<order_id>', methods=['DELETE'])
def delete_order(order_id):
    """Deleting Order -> Done by Shopkeeper"""
    order_manager = OrderManager(db)
    success = order_manager.delete_order(order_id)
    return jsonify({'successfully deleted': success})


#Payment
@app.route('/checkout', methods=['POST'])
def checkout():
    """Process checkout with customer and payment details. -> Extra"""
    # Validate input data
    data = request.json
    if not data:
        return jsonify({'error': 'No checkout data provided'}), 400

    # Extract customer and payment information
    customer_info = {
        'name': data.get('name', ''),
        'email': data.get('email', ''),
        'phone': data.get('phone', ''),
        'address': data.get('address', {
            'street': '',
            'city': '',
            'state': '',
            'zip': ''
        })
    }

    # Validate customer information
    if not customer_info['name'] or not customer_info['email']:
        return jsonify({'error': 'Name and email are required'}), 400

    # Validate credit card (basic validation)
    credit_card = data.get('payment', {})
    if not all([
        credit_card.get('card_number'),
        credit_card.get('expiry'),
        credit_card.get('cvv')
    ]):
        return jsonify({'error': 'Complete payment information required'}), 400

    # Existing cart and stock validation
    ensure_product_keys()
    ensure_cart_keys()

    cart_items = cart_table.all()
    if not cart_items:
        return jsonify({'error': 'Cart is empty'}), 400

    total_price = 0
    for item in cart_items:
        Product = Query()
        product = products_table.get(Product.name == item['name'])
        if product and product['stock'] >= item['quantity']:
            total_price += product['price'] * item['quantity']
            products_table.update(
                set('stock', product['stock'] - item['quantity']), 
                Product.id == product['id']
            )
        else:
            return jsonify({'error': f'Insufficient stock for {item["name"]}'}), 400

    # Create comprehensive order
    order = {
        'id': len(orders_table) + 1,
        'order_number': f'ORD-{len(orders_table) + 1}',
        'customer': customer_info,
        'items': cart_items,
        'total': round(total_price, 2),
        'payment_method': 'Credit Card',
        'payment_status': 'Processed',
        'timestamp': datetime.now().isoformat()
    }

    # Securely mask credit card details
    masked_card = {
        'last_four': credit_card['card_number'][-4:],
        'expiry': credit_card['expiry']
    }
    order['payment_details'] = masked_card

    # Insert order
    orders_table.insert(order)
    cart_table.truncate()  # Clear cart after successful checkout

    return jsonify({
        'message': 'Checkout successful', 
        'order_number': order['order_number'],
        'total_price': order['total']
    }), 201


#------------------------------------------------------------------------------------------------------


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
   