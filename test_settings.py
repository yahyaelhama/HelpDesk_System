"""
Test settings for email configuration
"""
# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = 'yahyaelhama@gmail.com'
EMAIL_HOST_PASSWORD = 'rknc lxft acew avgs'
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER 