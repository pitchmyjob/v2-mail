from flask import Flask, render_template, request
from flask_mail import Mail, Message
from flask_wtf import FlaskForm
from wtforms import Form, StringField
from wtforms.validators import DataRequired
from flask_wtf.file import FileField
from werkzeug.utils import secure_filename
from boto3.dynamodb.conditions import Key, Attr
import json
import urllib.request
import sys
import boto3
import datetime
import time
import uuid


# EB looks for an 'application' callable by default.
application = Flask(__name__)

application.config['MAIL_SERVER'] = 'email-smtp.eu-west-1.amazonaws.com'
application.config['MAIL_PORT'] = 587
application.config['MAIL_USERNAME'] = 'AKIAIQHHLEEWNNUS2SRA'
application.config['MAIL_PASSWORD'] = 'Ah4PYxyZLHkJFBNU+APGgvFkWHMGQvutaukZ4nRNTWzu'
application.config['MAIL_USE_TLS'] = True

application.config['WTF_CSRF_ENABLED'] = False
application.config['WTF_CSRF_SECRET_KEY'] = "xxxxxx"

mail = Mail(application)



class FormEmail(FlaskForm):
    to = StringField("to", validators=[DataRequired()])
    subject = StringField("subject", validators=[DataRequired()])
    ctx = StringField("ctx")
    template = StringField("template")
    from_email = StringField("from_email")
    file = FileField("file")
    url_file = StringField("url_file",)
    name_file = StringField("name_file")
    type_file = StringField("type_file")


class Emailing():

    def __init__(self, form):
        self.save = []
        self.field = {}

        session = boto3.session.Session(region_name="eu-west-1")
        dynamodb = session.resource('dynamodb')
        self.table = dynamodb.Table('Emailing')
        self.set_form(form)

    def set_form(self, form):
        self.field['subject']      = form.subject.data
        self.field['to']           = "".join(form.to.data.split()).split(',')
        self.field['name_file']    = form.name_file.data if form.name_file.data else "document.pdf"
        self.field['type_file']    = form.type_file.data if form.type_file.data else "application/pdf"
        self.field['ctx']          = json.loads(form.ctx.data) if form.ctx.data else json.loads("{}")
        self.field['from_email']   = form.from_email.data if form.from_email.data else "Pitch my job <contact@pitchmyjob.com>"
        self.field['template']     = form.template.data if form.template.data else "default.html"
        self.field['file']         = form.file.data
        self.field['url_file']     = form.url_file.data if form.url_file.data else None


    def save_pre_send(self):
        for email in self.field['to']:
            id = str(uuid.uuid4())
            self.save.append({'id' : id,'email' : email})
            now = datetime.datetime.now()
            self.table.put_item(
                Item={
                    'email_id': id,
                    'email': email,
                    'subject': self.field['subject'],
                    'template': self.field['template'],
                    'ctx': self.field['ctx'],
                    'datetime_sent': str(now),
                    'timestamp': int(time.mktime(now.timetuple())),
                    'date_sent': str(now.date()),
                    'time': { "hour" : str(now.time().strftime("%H")), "minute" : str(now.time().strftime("%M"))},
                    'sent' : 0,
                    'etat' : { "err" : 0 }
                }
            )

    def check_email(self, obj):
        dt = datetime.datetime.now()
        response = self.table.query(
            KeyConditionExpression=Key('email').eq(obj['email']),
            FilterExpression=Attr('sent').eq(1) & Attr('date_sent').eq(str(dt.date())) & Attr('time.hour').eq(dt.time().strftime("%H") ) & Attr('subject').eq(self.field['subject'])
        )

        if response['Count'] < 2 or obj['email'] == "tannier.yannis@gmail.com" :
            return True
        else :
            return False

    def update_email(self, obj):
        self.table.update_item(
            Key={
                'email': obj['email'],
                'email_id' : obj['id']
            },
            UpdateExpression="set sent = :val",
            ExpressionAttributeValues={
                ':val': 1
            }
        )

    def update_error(self, obj, exp, err):
        self.table.update_item(
            Key={
                'email': obj['email'],
                'email_id': obj['id']
            },
            UpdateExpression="set etat.err = :val, etat.message = :p",
            ExpressionAttributeValues={
                ':val': err,
                ':p' : str(exp)
            }
        )

    def send_email(self):
        msg = Message(self.field['subject'],
                      sender=self.field['from_email'],
                      recipients=self.field['to'] )

        msg.html = render_template(self.field['template'], obj=self.field['ctx'])
        if self.field['url_file']:
            file_name, headers = urllib.request.urlretrieve(self.field['url_file'])
            file = open(file_name, 'rb')
            msg.attach(self.field['name_file'], self.field['type_file'], file.read())
        if self.field['file'] :
            msg.attach(self.field['name_file'], self.field['type_file'], self.field['file'].read() )
        mail.send(msg)

    def handle_emailing(self):
        self.save_pre_send()

        for obj in self.save:
            if self.check_email(obj):
                try:
                    self.send_email()
                    self.update_email(obj)
                except Exception as exp:
                    self.update_error(obj, exp, 1)
            else:
                self.update_error(obj, "too many email", 2)


@application.route('/email', methods=['POST'])
def email():
    form = FormEmail()
    if form.validate_on_submit():
        Emailing(form).handle_emailing()
    return ""


@application.route('/')
def home():
    return "mail pitchmyjob"


@application.route('/test')
def test():
    msg = Message("Test",
                  sender="contact@pitchmyjob.com",
                  recipients=["tannier.yannis@gmail.com"])
    ctx = {
        "name": "Yannis",
        "job" : "Designer UX/UI",
        "image" : "https://www.pitchmyjob.com/media/c2v/4045/4045.jpg.50x50_q85_crop-smart.jpg",
        "users" : [
            {"name" : "Tannier Yannis", "image" : "https://www.pitchmyjob.com/media/c2v/4058/4058.jpg", "poste" : "Co-fondateur & CTO", "lieu" : "Paris, France"},
            {"name" : "Martial Dahan", "image" : "https://www.pitchmyjob.com/media/c2v/4058/4058.jpg", "poste" : "Co Fondateur et MACHINASS", "lieu" : "Paris, France"}
        ],
        "sender" : { "name" : "Martial Dahan", "image" : "https://www.pitchmyjob.com/media/c2v/4058/4058.jpg", "poste" : "Co-Fondateur", "company" : "Pitchmyjob"},
        "receiver" : { "name" : "Tannier Yannis"},
        "message" : " blabla bla  sdfsdf sdf sd fsd fdsfdsf sdf</br> blablabla </br> sdffsdfsdfsd"
    }

    msg.html = render_template("member/visite_profil.html", obj=ctx)
    mail.send(msg)
    return "mail pitchmyjob"


# run the app.
if __name__ == "__main__":
    if "dev" in sys.argv :
        application.debug = True
        application.run(host=application.config.get("HOST", "0.0.00"),port=application.config.get("PORT", 7070))
    else:
        application.run()