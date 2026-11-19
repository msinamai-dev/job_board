from paynow import Paynow

# Initialize Paynow client
paynow = Paynow(
    integration_id="YOUR_INTEGRATION_ID",
    integration_key="YOUR_INTEGRATION_KEY",
    result_url="https://yourdomain.com/payments/result/",  # webhook
    return_url="https://yourdomain.com/payments/return/"   # redirect after payment
)

def process_ecocash_payment(phone_number, amount, reference="Subscription Payment"):
    """Send EcoCash payment request via Paynow"""
    try:
        # Create payment
        payment = paynow.create_payment(reference, "sinamaimunoda@gmail.com")

        # Add item (subscription plan)
        payment.add("POS Subscription", float(amount))

        # Send payment request
        response = paynow.send_mobile(payment, phone_number, "ecocash")

        if response.success:
            # Redirect user if required
            redirect_url = response.redirect_url
            poll_url = response.poll_url  # Save in DB to check status later
            return {
                "success": True,
                "redirect_url": redirect_url,
                "poll_url": poll_url
            }
        else:
            return {"success": False, "error": response.errors}

    except Exception as e:
        return {"success": False, "error": str(e)}

def check_payment_status(poll_url):
    """Check if EcoCash payment has been confirmed"""
    try:
        status = paynow.check_transaction(poll_url)
        return {
            "paid": status.paid,
            "amount": status.amount,
            "status": status.status
        }
    except Exception as e:
        return {"paid": False, "error": str(e)}

def check_payment_status(poll_url):
    """Check if EcoCash payment has been confirmed"""
    try:
        status = paynow.check_transaction(poll_url)
        return {
            "paid": status.paid,
            "amount": status.amount,
            "status": status.status
        }
    except Exception as e:
        return {"paid": False, "error": str(e)}
