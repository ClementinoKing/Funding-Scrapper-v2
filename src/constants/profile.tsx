import {
  Building2,
  Store,
  Lightbulb,
} from 'lucide-react'

// Constants
export const BUSINESS_TYPES = [
  { id: 'registered', label: 'Registered Company', description: 'Formally registered with CIPC', icon: Building2, color: 'text-indigo-600' },
  { id: 'not-registered', label: 'Not Registered', description: 'Operating business, not formally registered', icon: Store, color: 'text-blue-600' },
  { id: 'spaza', label: 'Spaza Shop', description: 'Informal retail business', icon: Store, color: 'text-yellow-600' },
  { id: 'idea', label: 'Business Idea', description: 'Planning to start a business', icon: Lightbulb, color: 'text-orange-600' },
]

export const PROVINCES = [
  'Eastern Cape', 'Free State', 'Gauteng', 'KwaZulu-Natal',
  'Limpopo', 'Mpumalanga', 'Northern Cape', 'North West', 'Western Cape'
]

export const INDUSTRIES = [
  'Agriculture & Agro-processing',
  'Manufacturing',
  'Technology & IT',
  'Tourism & Hospitality',
  'Mining & Quarrying',
  'Energy & Utilities',
  'Healthcare & Pharmaceuticals',
  'Education & Training',
  'Retail & Wholesale',
  'Professional Services',
  'Construction & Real Estate',
  'Transport & Logistics',
  'Finance & Insurance',
  'Media & Communications',
  'Food & Beverage',
  'Textiles & Clothing',
  'Other',
]

export const FUNDING_PURPOSES = [
  'Working capital',
  'Equipment / Assets (vehicles, machinery, IT hardware)',
  'Technology / Digitisation (POS, accounting, ERP, e-commerce, cybersecurity)',
  'Property / Premises',
  'Marketing & Sales',
  'Research & Development',
  'Debt consolidation',
  'Expansion / Growth',
  'Other'
]

export const TIMELINE_OPTIONS = [
  { value: 'immediately', label: 'Immediately', description: 'Need funds ASAP (days)' },
  { value: '1-2-weeks', label: '1-2 weeks', description: 'Can wait a short while' },
  { value: 'within-month', label: 'Within a month', description: 'Planning ahead' },
  { value: '2-3-months', label: '2-3 months', description: 'Future planning' },
  { value: '3-plus-months', label: '3+ months', description: 'Longer lead items (grants, capex, equity)' },
  { value: 'flexible', label: "I'm flexible", description: 'Show me best options across timelines' },
]

export const STEPS = [
  { number: 1, title: 'Business Type', shortTitle: 'Type' },
  { number: 2, title: 'Business Details', shortTitle: 'Details' },
  { number: 3, title: 'Funding Needs', shortTitle: 'Funding' },
  { number: 4, title: 'Assessment', shortTitle: 'Assessment' },
]