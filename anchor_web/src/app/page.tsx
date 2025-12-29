'use client';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';

const COMPANIES = ['AAPL', 'MSFT', 'TSLA'];

export default function Home() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="flex justify-center items-center h-screen">Loading...</div>;
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-64px)] bg-white">
        <h1 className="text-4xl font-bold mb-4 text-prussian-blue">Welcome to Anchor</h1>
        <p className="text-xl text-onyx">Please log in to view companies.</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-6 text-prussian-blue">Companies</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {COMPANIES.map((company) => (
          <Link
            key={company}
            href={`/companies/${company}`}
            className="p-6 bg-white shadow rounded-lg border border-gray-200 hover:border-azure-blue transition-colors cursor-pointer block"
          >
            <h2 className="text-2xl font-semibold text-onyx">{company}</h2>
            <p className="mt-2 text-gray-500">Stock data and analysis for {company}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
