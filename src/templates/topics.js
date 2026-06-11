/**
 * Curated "Old Way vs AI Way" scenarios for solopreneurs.
 *
 * The ideation stage pulls from this list, then asks Claude to generate fresh
 * angles on whichever topics have NOT already been used (checked against the
 * Google Sheets log). Add to this list freely — more topics = more runway
 * before the agent starts repeating itself.
 */
export const TOPICS = [
  {
    id: "invoicing",
    label: "Invoicing & getting paid",
    oldWay: "Manually building invoices in Word, chasing payments over email",
    aiWay: "AI drafts, sends, and follows up on invoices from a single spreadsheet row"
  },
  {
    id: "content",
    label: "Content creation",
    oldWay: "Staring at a blank doc trying to write a week of posts",
    aiWay: "A spreadsheet + AI workflow that spins one idea into a week of content"
  },
  {
    id: "client-onboarding",
    label: "Client onboarding",
    oldWay: "Copy-pasting the same welcome emails and contracts for every new client",
    aiWay: "An AI-driven onboarding sheet that sends contracts, intake forms, and welcome sequences automatically"
  },
  {
    id: "bookkeeping",
    label: "Bookkeeping & expenses",
    oldWay: "Shoebox of receipts and a panicked spreadsheet every tax season",
    aiWay: "AI categorizes every expense into a live bookkeeping sheet as it happens"
  },
  {
    id: "email-management",
    label: "Email & inbox management",
    oldWay: "Drowning in an inbox, re-writing the same replies all day",
    aiWay: "AI triages, drafts, and templates replies straight from your inbox"
  },
  {
    id: "lead-tracking",
    label: "Lead tracking & follow-up",
    oldWay: "Leads scattered across DMs, sticky notes, and your memory",
    aiWay: "An AI CRM spreadsheet that scores leads and writes the follow-up for you"
  },
  {
    id: "scheduling",
    label: "Scheduling & calendar",
    oldWay: "Ten back-and-forth emails just to book one call",
    aiWay: "AI scheduling that reads intent and books the call in one reply"
  },
  {
    id: "proposals",
    label: "Proposals & quotes",
    oldWay: "Rebuilding a proposal from scratch for every prospect",
    aiWay: "AI generates a tailored proposal from a spreadsheet of your services"
  },
  {
    id: "social-analytics",
    label: "Social media analytics",
    oldWay: "Guessing what content worked from a messy notes app",
    aiWay: "A spreadsheet that pulls and analyzes your metrics with AI insights"
  },
  {
    id: "customer-support",
    label: "Customer support",
    oldWay: "Answering the same five questions over and over by hand",
    aiWay: "An AI support sheet that drafts answers from your FAQ knowledge base"
  },
  {
    id: "project-management",
    label: "Project & task management",
    oldWay: "A dozen half-finished to-do lists across three apps",
    aiWay: "One AI-powered project sheet that prioritizes and updates itself"
  },
  {
    id: "hiring-contractors",
    label: "Hiring contractors / VAs",
    oldWay: "Sifting through 80 applications by hand to find one good VA",
    aiWay: "AI screens and ranks applicants in a hiring spreadsheet"
  },
  {
    id: "inventory",
    label: "Inventory & ordering",
    oldWay: "Counting stock by hand and over-ordering every month",
    aiWay: "An AI inventory sheet that forecasts demand and flags reorders"
  },
  {
    id: "pricing",
    label: "Pricing your services",
    oldWay: "Picking prices out of thin air and undercharging",
    aiWay: "An AI pricing sheet that models margins and recommends rates"
  },
  {
    id: "newsletter",
    label: "Newsletter writing",
    oldWay: "Dreading the weekly newsletter and skipping weeks",
    aiWay: "An AI workflow that turns your week into a polished newsletter draft"
  }
];

/** Convenience: just the topic ids. */
export const TOPIC_IDS = TOPICS.map((t) => t.id);
