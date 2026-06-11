from pydantic import BaseModel, EmailStr


class RegisterForm(BaseModel):
    email: EmailStr
    display_name: str
    password: str


class LoginForm(BaseModel):
    email: EmailStr
    password: str
