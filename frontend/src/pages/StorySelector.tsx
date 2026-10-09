/**
 * Step 1 of 4 — Story Selector
 *
 * Allows the user to enter a Jira key or load the pre-baked sample story.
 * Displays a [SAMPLE DATA] banner when sample data is used.
 *
 * Implementation: placeholder UI — wired to backend in Milestone 2.
 */

export default function StorySelector() {
  return (
    <main style={{ maxWidth: 640, margin: '48px auto', fontFamily: 'system-ui, sans-serif' }}>
      <h1>Bob Intelligence</h1>
      <h2>Step 1 of 4 — Select a Story</h2>
      <p style={{ color: '#57606a' }}>
        Enter a Jira story key or load the sample story to begin.
      </p>
      <p style={{ background: '#fff8c5', border: '1px solid #d4a800', padding: '8px 12px', borderRadius: 4 }}>
        <strong>Milestone 2 required</strong> — story import not yet implemented.
      </p>
    </main>
  )
}
