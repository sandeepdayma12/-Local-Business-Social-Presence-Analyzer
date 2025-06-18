from django import forms

class BusinessSearchForm(forms.Form):
    city = forms.CharField(max_length=100, label="City Name")
    keyword = forms.CharField(max_length=100, label="Business Keyword")
