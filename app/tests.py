from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from rest_framework import status


class MeViewTest(APITestCase):

    def setUp(self):
        # ✅ test DB da user oldindan mavjud bo'lishi kerak
        self.user = User.objects.create_user(
            username="shaxlo",
            password="123456789$SH",
            email="shaxlo@test.com",
            first_name="Shaxlo",
        )
        self.url = "/app/me/"

    def test_get_me_success(self):
        fake_payload = {
            "preferred_username": "shaxlo",
            "email": "shaxlo@test.com",
            "name": "Shaxlo Test",
            "sub": "fake-uuid-123",
        }
        self.client.force_authenticate(user=self.user, token=fake_payload)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "shaxlo")

    def test_get_me_unauthorized(self):
        response = self.client.get(self.url)
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ])