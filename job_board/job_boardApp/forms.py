# payments/forms.py

from django import forms
from .models import PaymentProof

class PaymentProofForm(forms.ModelForm):
    class Meta:
        model = PaymentProof
        fields = ['image']
# posApp/forms.py

from django import forms
from .models import Department

PAGES = [
    ('dashboard', 'Dashboard'),
    ('sales', 'Sales'),
    ('products', 'Products'),
    ('subscriptions', 'Subscriptions'),
    ('users', 'Manage Users'),
]

class DepartmentForm(forms.ModelForm):
    allowed_pages = forms.MultipleChoiceField(
        choices=PAGES,
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Department
        fields = ['name', 'allowed_pages']

from django import forms
from .models import Shop

class ShopForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ['name', 'location']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter shop name'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter shop location'
            }),
        }
        labels = {
            'name': 'Shop Name',
            'location': 'Shop Location',
        }
from django import forms
from .models import Branch
from .models import ReceiptSettings

class ReceiptSettingsForm(forms.ModelForm):
    class Meta:
        model = ReceiptSettings
        fields = ["logo", "custom_header_name", "footer_text", "paper_width",
                  "margin_top", "margin_bottom", "show_timestamp", "auto_print"]

class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['name', 'location', 'shop', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'shop': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
from django import forms
from django.contrib.auth.models import User, Permission
from .models import Branch

class CustomUserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    branch = forms.ModelChoiceField(queryset=Branch.objects.none())
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'is_staff']

    def __init__(self, *args, **kwargs):
        shop = kwargs.pop('shop', None)
        super().__init__(*args, **kwargs)
        if shop:
            self.fields['branch'].queryset = Branch.objects.filter(shop=shop)
from django import forms

class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(label="Upload Excel File")

from django import forms
from django.contrib.auth.models import User

from .models import UserProfile, Shop, Branch, Department

class UserCreateForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    is_superuser = forms.BooleanField(required=False, label="Superuser")
    is_staff = forms.BooleanField(required=False, label="Staff")

    class Meta:
        model = User
        fields = ["username", "email", "password", "is_superuser", "is_staff"]
 

 

from django import forms
from django.apps import apps
from .models import UserProfile, Shop, Branch

PERMISSIONS = [
    ("view_dashboard", "View Dashboard"),
    ("view_products", "View Products"),
    ("view_categories", "View Categories"),
    ("manage_stocks", "Manage Stocks"),
    ("view_suppliers", "View Suppliers"),
    ("manage_purchase_orders", "Manage Purchase Orders"),
    ("view_credit_purchases", "View Purchases On Credits"),
    #("access_pos", "Access POS"),
    ("view_reports", "View Reports"),
    ("view_sales_report", "View Sales Report"),
    ("view_shift_report", "View Shift Report"),
    ("view_product_report", "View Product Report"),
    ("view_stock_tracker", "View Stock Tracker"),
    ("view_stock_history", "View Stock History"),
    ("manage_users", "Manage Users"),
    ("create_user", "Create User"),
    ("view_branch", "View Branch"),
    ("add_shop", "Add Shop"),
    ("view_shop", "View Shop"),
    ("view_users", "View Users"),
    ("user_edit", "user_edit"),
    ("user_list", "user_list"),
    ("user-delete", "user-delete"),
    ("manage_products", "manage_products"),
    ("stock_count","stock_count"),
    ("stock_adjustment","stock_adjustment"),
    ("stock_count_report","stock_count_report"),
    ("saleslist","saleslist"),
   ("user-list","user-list"),
   ("my-subscription","my-subscription"),
   ("subscription-plans","subscription-plans"),
   ("manage_subscriptions","manage_subscriptions"),
   ("stock_count","stock_count"),

    
    
    
]


class UserProfileForm(forms.ModelForm):
    permissions = forms.MultipleChoiceField(
        choices=PERMISSIONS,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="User Duties / Permissions"
    )
    subscribe_now = forms.BooleanField(required=False, label="Subscribe this user?")
    
    class Meta:
        model = UserProfile
        fields = [
            'phone_number',
            'country',
            'shop',
            'branch',
            'permissions',
            'access_rights',
        ]

    def __init__(self, *args, **kwargs):
        admin_user = kwargs.pop('admin_user', None)
        super().__init__(*args, **kwargs)

        

        # Filter shops and branches for this admin
        if admin_user and hasattr(admin_user, 'userprofile') and admin_user.userprofile.shop:
            self.fields['shop'].queryset = Shop.objects.filter(id=admin_user.userprofile.shop.id)
            self.fields['branch'].queryset = Branch.objects.filter(shop=admin_user.userprofile.shop)
        else:
            self.fields['shop'].queryset = Shop.objects.none()
            self.fields['branch'].queryset = Branch.objects.none()

from django import forms
from .models import Products, Branch
class TransferProductForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Products.objects.all())
    destination_branch = forms.ModelChoiceField(queryset=Branch.objects.all())
    quantity = forms.IntegerField()

