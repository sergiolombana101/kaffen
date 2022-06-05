from typing import OrderedDict
from django.conf import settings
from django.db import DEFAULT_DB_ALIAS
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.views.generic import ListView, DetailView, View
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .forms import CheckoutForm

from .models import (
    Item,
    OrderItem,
    Order,
    CheckoutAddress,
    Payment
)

import stripe
stripe.api_key = settings.STRIPE_KEY

class HomeView(ListView) :
    model = Item
    template_name = 'home.html'

class AboutView(ListView) :
    model = Item
    template_name = 'about.html'

class ProductView(DetailView) :
    model = Item
    template_name = "product.html"

class OrderSummaryView(LoginRequiredMixin, View) :
    def get(self, *args, **kwargs):

        try:
            order = Order.objects.get(user = self.request.user, ordered = False)
            context = {'object' : order}
            return render(self.request, 'order_summary.html', context)
        except ObjectDoesNotExist:
            messages.error(self.request, "You do not have an order")
            return redirect("/")

class CheckoutView(View) :
    def get(self, *args, **kwargs) :
        form = CheckoutForm()
        order = Order.objects.get(user=self.request.user, ordered = False)
        context = {
            'form' : form,
            'order' : order
        }
        return render(self.request, 'checkout.html', context)

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)

        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            order.ordered = True
            order.save()

            messages.warning(self.request, "Success Checkout")
            return redirect('core:order-confirmation', pk = order.id)

        except ObjectDoesNotExist:
            messages.error(self.request, "You do not have an order")
            return redirect("core:order-summary")

class ConfirmationView(View) :
    def get(self,*args, **kwargs):

        order_qs = Order.objects.filter(user = self.request.user, ordered = True)
        order = order_qs

        if order_qs.exists() :
            order = order_qs[len(order_qs)-1]

        context = {
            'order' : order
        }
        return render(self.request, 'confirmation.html', context)

class PaymentView(View):
    def get(self, *args, **kwargs):
        order = Order.objects.get(user = self.request.user, ordered = False)
        context = {
            'order' : order
        }
        return render(self.request, "payment.html", context)

    def post(self, *args, **kwargs):
        order = Order.objects.get(user = self.request.user, ordered = False)
        token = self.request.POST.get('stripeToken')
        amount = int(order.get_total_price() * 100) #cents

        try:
            charge = stripe.Charge.create(
                amount = amount,
                currency = 'usd',
                source = token
            )

            #create payment
              # create payment
            payment = Payment()
            payment.stripe_id = charge['id']
            payment.user = self.request.user
            payment.amount = order.get_total_price()
            payment.save()

            # assign payment to order
            order.ordered = True
            order.payment = payment
            order.save()

            messages.success(self.request, "Success make an order")
            return redirect('/')

        except stripe.error.CardError as e:
            body = e.json_body
            err = body.get('error', {})
            messages.error(self.request, f"{err.get('message')}")
            return redirect('/')

        except stripe.error.RateLimitError as e:
            # Too many requests made to the API too quickly
            messages.error(self.request, "To many request error")
            return redirect('/')

        except stripe.error.InvalidRequestError as e:
            # Invalid parameters were supplied to Stripe's API
            messages.error(self.request, "Invalid Parameter")
            return redirect('/')

        except stripe.error.AuthenticationError as e:
            # Authentication with Stripe's API failed
            # (maybe you changed API keys recently)
            messages.error(self.request, "Authentication with stripe failed")
            return redirect('/')

        except stripe.error.APIConnectionError as e:
            # Network communication with Stripe failed
            messages.error(self.request, "Network Error")
            return redirect('/')

        except stripe.error.StripeError as e:
            # Display a very generic error to the user, and maybe send
            # yourself an email
            messages.error(self.request, "Something went wrong")
            return redirect('/')
        
        except Exception as e:
            # Something else happened, completely unrelated to Stripe
            messages.error(self.request, "Not identified error")
            return redirect('/')

@login_required
def add_to_cart(request, pk) :
    item = get_object_or_404(Item, pk = pk)
    order_item, created = OrderItem.objects.get_or_create(
        item = item,
        user = request.user,
        ordered = False
    )

    order_qs = Order.objects.filter(user = request.user, ordered = False)

    if order_qs.exists() :
        order = order_qs[0]

        if order.items.filter(item__pk = item.pk).exists() :
            order_item.quantity += 1
            order_item.save()

            messages.info(request, "Added quantity Item")
            return redirect("core:order-summary")
        else:
            order.items.add(order_item)
            messages.info(request, "Item added to your cart")
            return redirect("core:order-summary")

    else : 
        ordered_date = timezone.now()
        order = Order.objects.create(user = request.user, ordered_date = ordered_date)
        order.items.add(order_item)
        messages.info(request, "Item added to your cart")
        return redirect("core:order-summary")

@login_required
def remove_from_cart(request, pk) :
    item = get_object_or_404(Item, pk = pk)
    order_qs = Order.objects.filter(
        user = request.user,
        ordered = False
    )

    if order_qs.exists():
        order = order_qs[0]

        if order.items.filter(item__pk = item.pk).exists():
            order_item = OrderItem.objects.filter(item = item, user = request.user, ordered = False)[0]
            order_item.delete()
            messages.info(request,
            "Item \"" + order_item.item.name + "\" removed from your cart")
            return redirect("core:order-summary")
        else:
            messages.info(request, "This item is not in your cart")
            return redirect("core:product", pk=pk)
    
    else:
        #Order does not exist
        messages.info(request, "You do not have an Order")
        return redirect("core:product", pk = pk)

@login_required
def reduce_quantity_item(request, pk):
    item = get_object_or_404(Item, pk = pk)
    order_qs = Order.objects.filter( user = request.user, ordered = False)

    if order_qs.exists():
        order = order_qs[0]

        if order.items.filter(item__pk = item.pk).exists() : 
            order_item = OrderItem.objects.filter(item = item, user = request.user, ordered = False)[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else :
                order_item.delete()
            messages.info(request, "Item quantity has been updated")
            return redirect("core:order-summary")
        else:
            messages.info(request, "This item is not in your cart")
            return redirect("core:order-summary")
    else:
        messages.info(request, "Order does not exist")
        return redirect("core:order-summary")