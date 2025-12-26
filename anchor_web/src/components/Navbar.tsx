'use client';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';

export default function Navbar() {
  const { user, signIn, signOut } = useAuth();

  return (
    <nav className="flex items-center justify-between p-4 bg-gray-800 text-white">
      <Link href="/" className="text-xl font-bold">
        Anchor
      </Link>
      <div className="flex gap-4">
        {user ? (
          <button
            onClick={signOut}
            className="px-4 py-2 bg-red-600 rounded hover:bg-red-700 transition-colors"
          >
            Sign Out
          </button>
        ) : (
          <>
            <button
              onClick={signIn}
              className="px-4 py-2 bg-blue-600 rounded hover:bg-blue-700 transition-colors"
            >
              Log In
            </button>
            <button
              onClick={signIn}
              className="px-4 py-2 bg-green-600 rounded hover:bg-green-700 transition-colors"
            >
              Sign Up
            </button>
          </>
        )}
      </div>
    </nav>
  );
}

