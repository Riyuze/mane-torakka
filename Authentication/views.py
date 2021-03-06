import threading
from django.shortcuts import render, redirect
from django.views import View
import json
from django.http import JsonResponse
from django.contrib.auth.models import User
from validate_email import validate_email
from django.contrib import messages, auth
from django.core.mail import EmailMessage

from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.sites.shortcuts import get_current_site

from django.urls import reverse

from .utils import token_generator

from django.contrib.auth.tokens import PasswordResetTokenGenerator

import threading

# Create your views here.

class EmailThread(threading.Thread):
    def __init__(self, email):
        self.email = email
        threading.Thread.__init__(self)

    def run(self):
        self.email.send(fail_silently=False)

class UsernameValidationView(View):
    def post(self, request):
        data = json.loads(request.body)
        username = data['username']

        if not str(username).isalnum():
            return JsonResponse({'username_error' : "Username should only contain letters and numbers"}, status=400)
        if User.objects.filter(username=username).exists():
            return JsonResponse({'username_error' : "Username taken, please choose another username"}, status=409)
        return JsonResponse({'username_valid' : True})


class EmailValidationView(View):
    def post(self, request):
        data = json.loads(request.body)
        email = data['email']

        if not validate_email(email):
            return JsonResponse({'email_error' : "Email is invalid"}, status=400)
        if User.objects.filter(email=email).exists():
            return JsonResponse({'email_error' : "Email taken, please choose another email"}, status=409)
        return JsonResponse({'email_valid' : True})

class RegistrationView(View):
    def get(self, request):
        return render(request, 'authentication/register.html')

    def post(self, request):
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']

        context = {
            'fieldValues': request.POST
        }

        if not User.objects.filter(username=username).exists():
            if not User.objects.filter(email=email).exists():
                if len(password) < 7:
                    messages.error(request, 'Password must be more than 7 characters!')
                    return render(request, 'authentication/register.html', context)
                
                user = User.objects.create_user(username=username, email=email)
                user.set_password(password)
                user.is_active = False
                user.save()

                uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
                token = token_generator.make_token(user)
                domain = get_current_site(request).domain
                link = reverse('activate', kwargs={'uidb64' : uidb64, 'token' : token})

                activate_url = "http://" + domain + link

                email_subject = "Activate your account"
                email_body = "Hi " + user.username + ", please use the link below to activate your account\n" + activate_url
                email = EmailMessage(
                    email_subject,
                    email_body,
                    'noreply@semycolon.com',
                    [email],
                )
                EmailThread(email).start()

                messages.success(request, 'Account successfully created, please check your email for activation instructions!')
                return render(request, 'authentication/register.html')

        return render(request, 'authentication/register.html')

class VerificationView(View):
    def get(self, request, uidb64, token):
        try:
            id = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=id)

            if not token_generator.check_token(user, token):
                return redirect('login' + '?message=' + 'Account already activated')

            if user.is_active:
                return redirect('login')
            user.is_active = True
            user.save()

            messages.success(request, 'Account activated succesfully!')
            return redirect('login')

        except Exception as ex:
            pass

        return redirect('login')

class LoginView(View):
    def get(self, request):
        return render(request, 'authentication/login.html')

    def post(self, request):
        username = request.POST['username']
        password = request.POST['password']

        if username and password:
            user = auth.authenticate(username=username, password=password)
            
            if user:
                if user.is_active:
                    auth.login(request, user)
                    messages.success(request, "Welcome, " + user.username + " you are now logged in")
                    return redirect('expenses')
            
                messages.warning(request, "Account is not activated yet, please check your email")
                return render(request, 'authentication/login.html')

            messages.error(request, "Invalid credentials, please try again")
            return render(request, 'authentication/login.html')
        
        messages.error(request, "Please fill all fields")
        return render(request, 'authentication/login.html')

class LogoutView(View):
    def post(self, request):
        auth.logout(request)
        messages.success(request, "You have been logged out")
        return redirect('login')

class ResetPassword(View):
    def get(self, request):
        return render(request, 'authentication/reset_password.html')

    def post(self, request):
        email = request.POST['email']

        context = {
            'fieldValues': request.POST
        }

        if not validate_email(email):
            messages.error(request, 'Please input a valid email')
            return render(request, 'authentication/reset_password.html', context)

        domain = get_current_site(request).domain

        user = User.objects.filter(email=email)

        if user.exists():        
            email_subject = "Password Reset Instructions"

            user = user[0]
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = PasswordResetTokenGenerator().make_token(user)
            link = reverse('set-new-password', kwargs={'uidb64' : uid, 'token' : token})
            reset_url = "http://" + domain + link

            email_body = "Hi, please use the link below to reset your password\n" + reset_url

            email = EmailMessage(
                email_subject,
                email_body,
                'noreply@semycolon.com',
                [email],
            )
            EmailThread(email).start()

            messages.success(request, 'We have sent you an email to reset your password')
        
        return render(request, 'authentication/reset_password.html')

class CompletePasswordReset(View):
    def get(self, request, uidb64, token):

        context = {
            'uidb64': uidb64,
            'token': token,
        }

        try:
            user_id = force_str(urlsafe_base64_decode(uidb64))

            user = User.objects.get(pk=user_id)
            
            if not PasswordResetTokenGenerator().check_token(user, token):
                messages.warning(request, "Link is invalid, please request a new one")
                return render(request, 'authentication/reset_password.html')
                
        except Exception:
            pass
        
        return render(request, 'authentication/set_new_password.html', context)

    def post(self, request, uidb64, token):

        context = {
            'uidb64': uidb64,
            'token': token,
        }

        password = request.POST['password']
        confirm_password = request.POST['confirm_password']

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return render(request, 'authentication/set_new_password.html', context)
        
        if len(password) < 7:
            messages.error(request, 'Password must be more than 7 characters!')
            return render(request, 'authentication/set_new_password.html', context)
        
        try:
            user_id = force_str(urlsafe_base64_decode(uidb64))

            user = User.objects.get(pk=user_id)
            user.set_password(password)
            user.save()

            messages.success(request, "Password reset successful")

            return redirect('login')
        except Exception:
            messages.warning(request, "Something went wrong, please try again")
            return render(request, 'authentication/set_new_password.html', context)