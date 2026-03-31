from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from rest_framework import status


class MeViewTest(APITestCase):

    def setUp(self):
        self.user, _ = User.objects.get_or_create(username="shaxlo")
        self.url = "/app/me/"

    def test_get_me_success(self):
        fake_payload = {
            "preferred_username": "admin",
            "email": "",
            "name": "Admin User",
        }
        self.client.force_authenticate(user=self.user, token=fake_payload)

        response = self.client.get(self.url)

        print("STATUS:", response.status_code)
        print("RESPONSE:", response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "admin")

    def test_get_me_unauthorized(self):
        response = self.client.get(self.url)

        print("STATUS:", response.status_code)

        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ])