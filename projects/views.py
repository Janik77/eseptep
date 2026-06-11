from django.shortcuts import render


def projects_home(request):
    return render(request, 'projects/home.html')
