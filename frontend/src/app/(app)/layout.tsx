import { UserButton } from "@clerk/nextjs";
import Link from "next/link";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-56 bg-slate-900 text-slate-100 flex flex-col py-6 px-4 gap-1 shrink-0">
        <Link href="/dashboard" className="text-lg font-bold text-white mb-6 px-2">
          DataProbe
        </Link>
        <NavLink href="/dashboard">Dashboard</NavLink>
        <NavLink href="/new">New Analysis</NavLink>
        <NavLink href="/reports">Reports</NavLink>
        <NavLink href="/sources">Sources</NavLink>
        <div className="mt-auto px-2 pt-6">
          <UserButton afterSignOutUrl="/" />
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-slate-50">{children}</main>
    </div>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
    >
      {children}
    </Link>
  );
}
