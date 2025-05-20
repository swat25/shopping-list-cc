from flask_sqlalchemy import SQLAlchemy
from datetime import datetime,timezone

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # FIXED: specify which FK to use
    lists = db.relationship(
        'GroceryList',
        backref='creator',
        lazy=True,
        foreign_keys='GroceryList.created_by'
    )

    # Lists the user has access to (via sharing)
    shared_lists = db.relationship(
        'ListShare',
        backref='user',
        cascade="all, delete-orphan"
    )



class GroceryList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id')) 
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    # Relationship to items (if not already added)
    items = db.relationship('GroceryItem', backref='grocery_list', cascade="all, delete-orphan", lazy=True)
   # To allow access to users this list is shared with
    shared_with = db.relationship('ListShare', backref='grocery_list', cascade="all, delete-orphan")



class GroceryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.String(50))
    list_id = db.Column(db.Integer, db.ForeignKey('grocery_list.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    added_by = db.Column(db.String(100))
    added_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User')
    
class ListShare(db.Model):
    __tablename__ = 'list_share'
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('grocery_list.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # Optional: enforce uniqueness so a user can’t be shared the same list multiple times
    __table_args__ = (db.UniqueConstraint('list_id', 'user_id', name='_list_user_uc'),)


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    is_purchased = db.Column(db.Boolean, default=False)
    list_id = db.Column(db.Integer, db.ForeignKey('grocery_list.id'), nullable=False)

