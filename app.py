
import base64
import streamlit as st
import joblib

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


MODEL_PATH = "spam_detection_model.pkl"


def get_email_body(payload):
    body = ""

    if "parts" in payload:
        for part in payload["parts"]:
            body += get_email_body(part)
    else:
        mime_type = payload.get("mimeType", "")
        data = payload.get("body", {}).get("data")

        if mime_type == "text/plain" and data:
            try:
                body += base64.urlsafe_b64decode(data).decode(
                    "utf-8", errors="ignore"
                )
            except Exception:
                pass

    return body


def get_gmail_service():
    access_token = st.user.tokens["access"]

    credentials = Credentials(token=access_token)

    return build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False
    )


def get_all_messages(service):
    all_messages = []
    page_token = None

    while True:
        response = service.users().messages().list(
            userId="me",
            q="-in:spam -in:trash",
            maxResults=500,
            pageToken=page_token
        ).execute()

        all_messages.extend(response.get("messages", []))

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return all_messages


st.set_page_config(
    page_title="Email Spam Detection",
    page_icon="📧"
)

st.title("📧 Email Spam Detection")

# --------------------------------------------------
# LOGIN SCREEN
# --------------------------------------------------

if not st.user.is_logged_in:

    st.header("Connect your Gmail")

    st.write(
        "Sign in with your Google account to analyze your Gmail messages."
    )

    st.button(
        "🔗 Login with Google",
        on_click=st.login
    )

    st.stop()


# --------------------------------------------------
# LOGGED-IN USER
# --------------------------------------------------

st.success(f"Connected Gmail: {st.user.email}")

if st.button("Logout"):
    st.logout()

st.write(
    "Click the button below to classify all available Gmail messages."
)


# --------------------------------------------------
# CLASSIFY EMAILS
# --------------------------------------------------

if st.button("🔍 Detect Spam in All Gmail Messages"):

    try:

        model = joblib.load(MODEL_PATH)

        service = get_gmail_service()

        st.info("Getting your Gmail messages...")

        messages = get_all_messages(service)

        total = len(messages)

        if total == 0:
            st.warning("No Gmail messages found.")
            st.stop()

        st.success(f"Found {total} Gmail messages.")

        spam_count = 0
        not_spam_count = 0

        progress = st.progress(0)

        for index, message in enumerate(messages):

            email_data = service.users().messages().get(
                userId="me",
                id=message["id"],
                format="full"
            ).execute()

            payload = email_data.get("payload", {})
            headers = payload.get("headers", [])

            sender = "Unknown Sender"
            subject = "No Subject"

            for header in headers:

                name = header["name"].lower()

                if name == "from":
                    sender = header["value"]

                elif name == "subject":
                    subject = header["value"]

            body = get_email_body(payload)

            email_text = subject + " " + body

            prediction = model.predict([email_text])[0]

            st.divider()

            st.write("**From:**", sender)
            st.write("**Subject:**", subject)

            if prediction == "spam":

                st.error("🚨 SPAM")
                spam_count += 1

            else:

                st.success("✅ NOT SPAM")
                not_spam_count += 1

            progress.progress((index + 1) / total)

        st.divider()

        st.subheader("📊 Classification Summary")

        st.write("🚨 Spam:", spam_count)
        st.write("✅ Not Spam:", not_spam_count)
        st.write("📧 Total:", total)

        st.success("✅ All Gmail messages have been classified!")

    except HttpError as e:

        st.error(
            "Gmail API error. Please log out and sign in again."
        )

    except Exception as e:

        st.error(
            "Something went wrong while accessing Gmail."
        )
