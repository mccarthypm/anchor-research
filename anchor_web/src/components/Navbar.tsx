'use client';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';

export default function Navbar() {
  const { user, signIn, signOut } = useAuth();

  return (
    <nav className="flex items-center justify-between p-4 bg-white text-onyx shadow-md">
      <Link href="/" className="text-xl font-bold text-azure-blue">
        Anchor
      </Link>
      <div className="flex gap-4">
        {user ? (
          <button
            onClick={signOut}
            className="px-4 py-2 bg-raspberry-red text-white rounded hover:opacity-90 transition-opacity"
          >
            Sign Out
          </button>
        ) : (
          <>
            <button
              onClick={signIn}
              className="px-4 py-2 bg-azure-blue text-white rounded hover:opacity-90 transition-opacity"
            >
              Log In
            </button>
          </>
        )}
      </div>
    </nav>
  );
}

