-- Migration 006: Auth profiles table
-- Creates a profiles table linked to Supabase auth.users for role management.
-- Run in Supabase SQL Editor.

-- Profiles table: stores role for each authenticated user
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Enable RLS
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Users can read their own profile
CREATE POLICY "Users read own profile"
    ON public.profiles FOR SELECT
    USING (auth.uid() = id);

-- Service role can read all profiles (for server-side role lookup)
CREATE POLICY "Service role reads all profiles"
    ON public.profiles FOR SELECT
    USING (auth.role() = 'service_role');

-- Auto-create profile row when a new user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, role)
    VALUES (NEW.id, NEW.email, 'user');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- After first Google sign-in, promote admin manually:
-- UPDATE public.profiles SET role = 'admin' WHERE email = 'your@gmail.com';
