# app/models.py
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from datetime import datetime

class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_complete = db.Column(db.Boolean, default=False, nullable=False)
    # This field will be skipped in the form
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # This field will appear as a DateField in the form
    due_date = db.Column(db.Date, nullable=True)
    # This field will be auto-populated by current_user.id
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    author = db.relationship('User', 
                             backref=db.backref('tasks', 
                                                lazy=True, 
                                                cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<Task {self.title}>'


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    def __repr__(self):
        return f'<Category {self.name}>'

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, default=0, nullable=False)
    # This field will be skipped in the form (default=datetime.utcnow)
    date_added = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # This field will be auto-populated by current_user.id
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # This field will be skipped in the form (ForeignKey)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    author = db.relationship('User', 
                             backref=db.backref('products', 
                                                lazy=True, 
                                                cascade='all, delete-orphan'))
    category = db.relationship('Category', 
                               backref=db.backref('products', 
                                                  lazy=True))

    def __repr__(self):
        return f'<Product {self.name}>'

