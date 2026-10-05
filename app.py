from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_manager, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, PrimaryKeyConstraint, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
import bleach
from dotenv import load_dotenv
import os
import hashlib


'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''
load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

@app.template_filter('gravatar')
def gravatar_url(email):
    # Convert the email to lowercase, encode it, and hash it with MD5
    email_hash = hashlib.md5(email.lower().encode('utf-8')).hexdigest()
    # Return the URL matching Gravatar's exact requirements
    return f"https://www.gravatar.com/avatar/{email_hash}?s=100&d=retro&r=g"

# TODO: Configure Flask-Login


# CREATE DATABASE
class Base(DeclarativeBase):
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB_URI','sqlite:///blog.db')
db = SQLAlchemy(model_class=Base)
db.init_app(app)

login_manager1 = LoginManager()
login_manager1.login_view = "login"
login_manager1.init_app(app)

def admin_only(f):
    @wraps(f)
    def decorated_function(*args,**kwargs):
        if current_user.is_authenticated and current_user.id == 1:
            return f(*args,**kwargs)
        else:
            abort(403)
            # return redirect(url_for('login',next=request.url))
    return decorated_function

@login_manager1.user_loader
def load_user(user_id):
    return db.session.get(User,user_id)



# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    author_id:Mapped[int]=mapped_column(Integer,ForeignKey("users.id"),nullable=False)
    author=relationship("User",back_populates="posts")
    comments=relationship("Comment",back_populates="post")



# TODO: Create a User table for all your registered users. 

class User(db.Model,UserMixin):
    __tablename__="users"
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    name:Mapped[str] = mapped_column(String(250),nullable=False)
    email:Mapped[str] = mapped_column(String(250),unique=True,nullable=False)
    password:Mapped[str] = mapped_column(String(256),nullable=False)
    posts=relationship("BlogPost",back_populates="author")
    comments=relationship("Comment",back_populates="commenter")

class Comment(db.Model):
    __tablename__="comments"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    text:Mapped[str]=mapped_column(String(524),nullable=False)
    commenter_id:Mapped[int]=mapped_column(Integer,ForeignKey("users.id"))
    commenter=relationship("User",back_populates="comments")
    post_id:Mapped[int]=mapped_column(Integer,ForeignKey("blog_posts.id"))
    post=relationship("BlogPost",back_populates="comments")

# with app.app_context():
#     db.create_all()


# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register',methods=["GET","POST"])

def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if db.session.execute(db.select(User).where(User.email == form.email.data)).scalar() is  None:
            new_user = User(
                name=form.name.data,
                email=form.email.data,
                password = generate_password_hash(salt_length=12,password=form.password.data,method="scrypt")
                )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)

            return redirect(url_for("get_all_posts"))
        else:
            flash("Email already registered")
            return redirect(url_for("register"))

    return render_template("register.html",form=form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=['GET','POST'])
def login():
    form=LoginForm()
    if form.validate_on_submit():
        the_user= db.session.execute(db.select(User).where(User.email==form.email.data)).scalar()
        if the_user is not None:
            if check_password_hash(the_user.password,form.password.data):
                login_user(the_user)
                if request.args.get('next'):
                    return redirect(request.args.get('next'))
                return redirect(url_for("get_all_posts"))


        flash("Email or Password is incorrect")

    return render_template("login.html",form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>",methods=['GET','POST'])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    form=CommentForm()
    if form.validate_on_submit():
        if current_user.is_authenticated:

            #when using ckeditor not necessary to use bleach
            # define the list of tags first
            allowed_tags = ['p', 'b', 'i', 'em', 'strong', 'a', 'ul', 'ol', 'li']
            # Scrub the incoming data
            clean_text = bleach.clean(form.comment.data, tags=allowed_tags, strip=True)

            new_comment = Comment(
                text=clean_text,
                commenter=current_user,
                post=requested_post
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=requested_post.id))
        else:
            return redirect(url_for('login',next=request.url))

    return render_template("post.html", post=requested_post, form=form)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)

# def

# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author.name,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=False)
