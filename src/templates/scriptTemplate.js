/**
 * The "Old Way vs AI Way" script template.
 *
 * Every Kaley AI video follows the same five-beat structure. This module holds
 * the canonical structure description that gets injected into the scriptwriting
 * prompt, plus a helper to flatten a structured script into a single narration
 * string for the voiceover stage.
 */

export const SCRIPT_STRUCTURE = `
Structure every script as exactly these five beats:

1. HOOK (2-4s): A punchy, scroll-stopping opener that names the pain or the
   promise. Often "The old way of <task> vs the AI way." Make the viewer feel
   called out.
2. OLD WAY (8-12s): Paint the tedious, manual, soul-draining traditional
   workflow. Be specific and a little tongue-in-cheek about how painful it is.
3. AI WAY (8-12s): Reveal the AI + spreadsheet workflow that replaces it. Make
   it sound almost unfairly easy. Reference a spreadsheet/AI system.
4. PROOF (5-8s): A concrete, believable result — time saved, money kept, stress
   gone. A number lands well ("from 3 hours to 3 minutes").
5. CTA (2-4s): Tell them to follow for more AI workflows and tease the template
   line, without being salesy.

Total spoken length must fit 30-45 seconds when read at a natural pace
(roughly 80-120 words total).
`.trim();

/**
 * Flatten a structured script object into a single narration string.
 * @param {{hook:string, oldWay:string, aiWay:string, proof:string, cta:string}} script
 * @returns {string}
 */
export function toNarration(script) {
  return [script.hook, script.oldWay, script.aiWay, script.proof, script.cta]
    .filter(Boolean)
    .map((s) => s.trim())
    .join(" ");
}
