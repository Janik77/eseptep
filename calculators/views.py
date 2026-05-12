from django.shortcuts import render


def calculators_home(request):
    return render(request, 'calculators/home.html')
