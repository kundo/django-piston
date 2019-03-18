from __future__ import absolute_import

import time

# Django imports
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.utils.http import urlencode
from six.moves.urllib.parse import urlparse, urlunparse

from .managers import ConsumerManager, TokenManager
from .signals import consumer_post_delete, consumer_post_save

KEY_SIZE = 18
SECRET_SIZE = 32
VERIFIER_SIZE = 10

CONSUMER_STATES = (
    ('pending', 'Pending'),
    ('accepted', 'Accepted'),
    ('canceled', 'Canceled'),
    ('rejected', 'Rejected')
)


AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


def generate_random(length=SECRET_SIZE):
    return User.objects.make_random_password(length=length)

class Nonce(models.Model):
    token_key = models.CharField(max_length=KEY_SIZE)
    consumer_key = models.CharField(max_length=KEY_SIZE)
    key = models.CharField(max_length=255)

    def __unicode__(self):
        return u"Nonce %s for %s" % (self.key, self.consumer_key)


class Consumer(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()

    key = models.CharField(max_length=KEY_SIZE)
    secret = models.CharField(max_length=SECRET_SIZE)

    status = models.CharField(max_length=16, choices=CONSUMER_STATES, default='pending')
    user = models.ForeignKey(AUTH_USER_MODEL,
                             null=True, blank=True, related_name='consumers',
                             on_delete=models.CASCADE)

    objects = ConsumerManager()

    def __unicode__(self):
        return u"Consumer %s with key %s" % (self.name, self.key)

    def generate_random_codes(self):
        """
        Used to generate random key/secret pairings. Use this after you've
        added the other data in place of save().

        c = Consumer()
        c.name = "My consumer"
        c.description = "An app that makes ponies from the API."
        c.user = some_user_object
        c.generate_random_codes()
        """
        key = User.objects.make_random_password(length=KEY_SIZE)
        secret = generate_random(SECRET_SIZE)

        while Consumer.objects.filter(key__exact=key, secret__exact=secret).count():
            secret = generate_random(SECRET_SIZE)

        self.key = key
        self.secret = secret
        self.save()


class Token(models.Model):
    REQUEST = 1
    ACCESS = 2
    TOKEN_TYPES = ((REQUEST, u'Request'), (ACCESS, u'Access'))

    key = models.CharField(max_length=KEY_SIZE)
    secret = models.CharField(max_length=SECRET_SIZE)
    verifier = models.CharField(max_length=VERIFIER_SIZE)
    token_type = models.IntegerField(choices=TOKEN_TYPES)
    timestamp = models.IntegerField(default=int(time.time()))
    is_approved = models.BooleanField(default=False)

    user = models.ForeignKey(AUTH_USER_MODEL, null=True, blank=True,
                             related_name='tokens',
                             on_delete=models.CASCADE)
    consumer = models.ForeignKey(Consumer, on_delete=models.CASCADE)

    callback = models.CharField(max_length=255, null=True, blank=True)
    callback_confirmed = models.BooleanField(default=False)

    objects = TokenManager()

    def __unicode__(self):
        return u"%s Token %s for %s" % (self.get_token_type_display(), self.key, self.consumer)

    def to_string(self, only_key=False):
        token_dict = {
            'oauth_token': self.key,
            'oauth_token_secret': self.secret,
            'oauth_callback_confirmed': 'true',
        }

        if self.verifier:
            token_dict.update({ 'oauth_verifier': self.verifier })

        if only_key:
            del token_dict['oauth_token_secret']

        return urlencode(token_dict)

    def generate_random_codes(self):
        key = User.objects.make_random_password(length=KEY_SIZE)
        secret = generate_random(SECRET_SIZE)

        while Token.objects.filter(key__exact=key, secret__exact=secret).count():
            secret = generate_random(SECRET_SIZE)

        self.key = key
        self.secret = secret
        self.save()

    # -- OAuth 1.0a stuff

    def get_callback_url(self):
        if self.callback and self.verifier:
            # Append the oauth_verifier.
            parts = urlparse(self.callback)
            scheme, netloc, path, params, query, fragment = parts[:6]
            if query:
                query = '%s&oauth_verifier=%s' % (query, self.verifier)
            else:
                query = 'oauth_verifier=%s' % self.verifier
            return urlunparse((scheme, netloc, path, params,
                query, fragment))
        return self.callback

    def set_callback(self, callback):
        if callback != "oob": # out of band, says "we can't do this!"
            self.callback = callback
            self.callback_confirmed = True
            self.save()


# Attach our signals
post_save.connect(consumer_post_save, sender=Consumer)
post_delete.connect(consumer_post_delete, sender=Consumer)
