import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/auth-store";
import { signUpWithSupabase } from "@/services/auth/supabase-auth";
import { toast } from "sonner";

export function RegisterPage() {
  const navigate = useNavigate();
  const setSession = useAuthStore((state) => state.setSession);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <CardTitle>Create your FundMatch account</CardTitle>
          <CardDescription>
            Start with core details. You will complete a full matching profile next.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4 md:grid-cols-2"
            onSubmit={async (event) => {
              event.preventDefault();
              setError(null);
              setLoading(true);
              const formData = new FormData(event.currentTarget);
              const firstName = String(formData.get("fullName") || "").trim();
              const lastName = String(formData.get("lastName") || "").trim();
              const fullName = [firstName, lastName].filter(Boolean).join(" ").trim();
              const email = String(formData.get("email") || "").trim();
              const password = String(formData.get("password") || "");
              try {
                const session = await signUpWithSupabase(email, password, fullName);
                if (session) {
                  setSession({
                    user: {
                      id: session.user.id,
                      name: session.user.fullName,
                      email: session.user.email,
                      role: session.user.role
                    },
                    accessToken: session.accessToken,
                    refreshToken: session.refreshToken
                  });
                  navigate("/app/dashboard");
                  return;
                }
                navigate("/auth/login");
              } catch (registerError) {
                const message = registerError instanceof Error ? registerError.message : "Unable to create account.";
                setError(message);
                toast.error(message);
              } finally {
                setLoading(false);
              }
            }}
          >
            <div className="space-y-2">
              <Label>First name</Label>
              <Input name="fullName" required />
            </div>
            <div className="space-y-2">
              <Label>Last name</Label>
              <Input name="lastName" required />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label>Email</Label>
              <Input name="email" type="email" required />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label>Password</Label>
              <Input name="password" type="password" required />
            </div>
            {error ? <p className="md:col-span-2 text-sm text-destructive">{error}</p> : null}
            <div className="md:col-span-2">
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Creating account..." : "Create Account"}
              </Button>
            </div>
          </form>
          <p className="mt-4 text-sm text-muted-foreground">
            Already have an account? <Link to="/auth/login" className="font-semibold text-primary">Sign in</Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
