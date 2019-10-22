def test_can_setup_piston():
    import django
    from django.conf import settings
    settings.configure(
        INSTALLED_APPS=[
            # Piston needs these apps
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sites",
            # Piston itself
            "piston",
        ],
    )
    django.setup()

    from piston.handler import AnonymousBaseHandler
    from piston.utils import rc
    from piston.resource import Resource
