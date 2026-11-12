from django.contrib import admin

from .models import Charity, CharityDomain, CharityLocation, Domain, Haskama, Link, Location, Review

admin.site.register([Charity, Location, Domain, CharityDomain, CharityLocation, Link, Review, Haskama])
