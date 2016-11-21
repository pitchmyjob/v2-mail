from flask import Flask, render_template, request
from flask_mail import Mail, Message
from flask_wtf import FlaskForm
from wtforms import Form, StringField, IntegerField
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

#application.config['MAIL_SERVER'] = 'in-v3.mailjet.com'
#application.config['MAIL_PORT'] = 25
#application.config['MAIL_USERNAME'] = '716554e44256731439609ad75c0c64eb'
#application.config['MAIL_PASSWORD'] = '4fe406245518835c398c0e8bf8f74209'
#application.config['MAIL_USE_TLS'] = False

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
    secure   = IntegerField("secure")


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
        self.field['secure']       = form.secure.data if form.secure.data else 1


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

        if self.field['secure'] == 1 :
            condition = Attr('sent').eq(1) & Attr('date_sent').eq(str(dt.date())) & Attr('time.hour').eq(dt.time().strftime("%H") ) & Attr('subject').eq(self.field['subject'])

        if self.field['secure'] == 2 :
            condition = Attr('sent').eq(1) & Attr('date_sent').eq(str(dt.date())) & Attr('subject').eq(self.field['subject'])

        response = self.table.query(
            KeyConditionExpression=Key('email').eq(obj['email']),
            FilterExpression=condition
        )

        if response['Count'] < 1 or obj['email'] == "tannier.yannis@gmail.com" :
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
    return ""


# run the app.
if __name__ == "__main__":
    if "dev" in sys.argv :
        application.debug = True
        application.run(host=application.config.get("HOST", "0.0.00"),port=application.config.get("PORT", 7070))
    else:
        application.run()
