import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { Bell, LogOut, Menu, Search } from "lucide-react";
import { useState } from "react";
import { navByRole } from "@/config/navigation";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  if (!user) return null;

  const navItems = navByRole[user.role];

  return (
    <div className="min-h-screen">
      <div className="flex min-h-screen w-full">
        <aside
          className={cn(
            "fixed inset-y-0 left-0 z-40 w-72 border-r border-emerald-900/20 bg-[#0e1412] text-zinc-100 transition-transform lg:static lg:translate-x-0",
            menuOpen ? "translate-x-0" : "-translate-x-full"
          )}
        >
          <div className="flex h-16 items-center border-b border-emerald-900/20 px-6">
            <Link to="/" className="text-lg font-bold tracking-tight">
              FundMatch Pro
            </Link>
          </div>
          <nav className="space-y-1 p-4">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "block rounded-sm px-3 py-2 text-sm font-medium transition",
                    isActive
                      ? "bg-emerald-500 text-emerald-950"
                      : "text-zinc-300 hover:bg-emerald-500/10 hover:text-zinc-100"
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="w-full flex-1 lg:ml-0">
          <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur-sm">
            <div className="flex h-16 items-center gap-3 px-4 lg:px-8">
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                onClick={() => setMenuOpen((prev) => !prev)}
              >
                <Menu className="h-5 w-5" />
              </Button>
              <div className="relative hidden w-full max-w-md md:block">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input placeholder="Search programs, sectors, providers..." className="pl-9" />
              </div>
              <div className="ml-auto flex items-center gap-2">
                <Button variant="ghost" size="icon">
                  <Bell className="h-4 w-4" />
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button className="flex items-center gap-2 rounded-md px-2 py-1 hover:bg-secondary">
                      <Avatar className="h-8 w-8">
                        <AvatarFallback>{user.name.slice(0, 2).toUpperCase()}</AvatarFallback>
                      </Avatar>
                      <span className="hidden text-sm font-medium md:block">{user.name}</span>
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => navigate("/")}>Go Home</DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        logout();
                        navigate("/auth/login");
                      }}
                    >
                      <LogOut className="mr-2 h-4 w-4" />
                      Sign Out
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </header>
          <div className="p-4 lg:p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
