// Survey URL — single source of truth (imported by SurveyPage.ts)
export const BASE_URL =
  process.env.BASE_URL || '{{BASE_URL}}'

// Q_TEXT: question text constants used in assertions (update to match your app)
export const Q_TEXT = {
  welcome:  'Share your feedback',
  q1NpsLow: 'Not likely at all',
  q1NpsHigh: 'Extremely likely',
  q2Intro:  'You provided a rating of',
  q2Suffix: 'please provide reason(s).',
  q3Low:    'Very Dissatisfied',
  q3High:   'Very Satisfied',
  q35:      'Any additional suggestions, please comment.',
  thankYou: /Thank you/i,
} as const

// Default test data for flow helpers (change here = changes everywhere)
export const TEST_DATA = {
  npsScore:           8,
  reason:             'Test reason',
  overallRating:      4,
  satisfactionRating: 3,
} as const
