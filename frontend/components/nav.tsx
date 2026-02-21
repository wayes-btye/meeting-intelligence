"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { ApiStatus } from "./api-status";
import { createClient } from "@/lib/supabase";
import { Button } from "@/components/ui/button";

const links = [
  { href: "/", label: "Upload" },
  { href: "/chat", label: "Chat" },
  { href: "/meetings", label: "Meetings" },
];

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  const isLoginPage = pathname === "/login";

  return (
    <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-8">
          <Link href="/" className="font-bold text-lg tracking-tight">
            Meeting Intelligence
          </Link>
          {!isLoginPage && (
            <nav className="flex items-center gap-1">
              {links.map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-sm font-medium transition-colors hover:bg-muted",
                    pathname === href
                      ? "bg-muted text-foreground"
                      : "text-muted-foreground",
                  )}
                >
                  {label}
                </Link>
              ))}
            </nav>
          )}
        </div>
        {!isLoginPage && (
          <div className="flex items-center gap-3">
            <ApiStatus />
            <Button variant="outline" size="sm" onClick={handleSignOut}>
              Sign out
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}
