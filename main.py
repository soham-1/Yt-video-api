from datetime import timedelta

import config

from flask import Flask, jsonify, render_template, url_for, session, redirect
from flask_restful import Api, abort, Resource, fields, marshal_with, marshal
from flask_sqlalchemy import SQLAlchemy

from authlib.integrations.flask_client import OAuth
from pytube import YouTube
import pafy

app = Flask(__name__)
api = Api(app)

app.config['SECRET_KEY'] = config.secret_key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

global client_id
global client_secret

client_id = config.client_id
client_secret = config.client_secret

# Session config
app.config['SESSION_COOKIE_NAME'] = 'google-login-session'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=5)

# oAuth Setup
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=client_id,
    client_secret=client_secret,
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    client_kwargs={'scope': 'openid email profile'},
)

class VideoModel(db.Model):
    video_id = db.Column(db.String, primary_key=True)
    title = db.Column(db.String, nullable=False)
    length = db.Column(db.String, nullable=False)
    views = db.Column(db.Integer, nullable=False, default=0) 
    likes = db.Column(db.Integer, nullable=False, default=0) 

resource_fields = {
    'video_id': fields.String,
	'title': fields.String,
    'length': fields.String,
	'views': fields.Integer,
	'likes': fields.Integer
}

@app.route('/')
def index():
    return render_template('index.html')

class Yt_videos(Resource):
    def get(self, video_id, resolution):
        """
        returns video specified by id and resolution
        resolution format - 144p,360p,...
        """
        video = VideoModel.query.filter_by(video_id=video_id).first()
        return {'id':video.video_id, 'title':video.title, 'length':video.length, 'views':video.views, 'likes':video.likes}
    
    @marshal_with(resource_fields)
    def put(self, video_id, resolution):
        """
        downloads video specified by id and resolution in videos folder (an directory above)
        returns metadata of specified video
        resolution format - 144p,360p,...
        """
        url = "https://www.youtube.com/watch?v=" + video_id
        url_obj = YouTube(url)
        pafy_obj = pafy.new(url)
        download(url_obj, resolution)
        result = VideoModel.query.filter_by(video_id=video_id).first()
        video = VideoModel(video_id=video_id, title=url_obj.title, length=pafy_obj.duration, views=url_obj.views, likes=pafy_obj.likes)
        if result is None:
            db.session.add(video)  
            db.session.commit()
        return video, 201

def download(url_obj, resolution):
    try:
        video = url_obj.streams.filter(res=resolution).first()
        video.download("../videos")
    except Exception as e:
        print("video download failed")

@app.route('/listVideos/<int:page_num>', methods=['GET'])
def paginate_video(page_num):
    pages = VideoModel.query.paginate(per_page=1, page=page_num, error_out=True)
    return render_template('paginate_videos.html', pages=pages)

@app.route('/listVideos/filter_views/<int:page_num>/<int:views>', methods=['GET'])
def paginate_video_by_views(page_num, views):
    """filters video with greater no. of likes than specified"""
    pages = VideoModel.query.filter(VideoModel.views >= views).paginate(per_page=1, page=page_num, error_out=True)
    return render_template('paginate_videos.html', pages=pages, views=views)

@app.route('/listVideos/filter_likes/<int:page_num>/<int:likes>', methods=['GET'])
def paginate_video_by_likes(page_num, likes):
    """filters video by no. greater likes than specified"""
    pages = VideoModel.query.filter(VideoModel.likes >= likes).paginate(per_page=1, page=page_num, error_out=True)
    return render_template('paginate_videos.html', pages=pages, likes=likes)

@app.route('/ytVideo/all', methods=['GET'])
def get_all():
    """list all videos added to database"""
    all_videos = [{'id':video.video_id, 'title':video.title, 'length':video.length, 'views':video.views, 'likes':video.likes} for video in VideoModel.query.all()]
    return jsonify(all_videos)

@app.route('/login')
def login():
    google = oauth.create_client('google')
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    google = oauth.create_client('google')
    token = google.authorize_access_token()
    resp = google.get('userinfo')
    user_info = resp.json()
    user = oauth.google.userinfo()
    session['profile'] = user_info
    session.permanent = True
    return redirect(url_for('get_all'))

@app.route('/logout')
def logout():
    for key in list(session.keys()):
        session.pop(key)
    return redirect('/')

def isLoggedIN():
    try:
        user = dict(session).get('profile', None)
        if user:
            return True, user.get("given_name")
        else:
            return False,{}
    except Exception as e:
        return False,{}

api.add_resource(Yt_videos, "/ytVideo/<string:video_id>/<string:resolution>")

if __name__ == "__main__":
    app.run(debug=True)
    