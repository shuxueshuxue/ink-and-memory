export default function AboutView() {
  return (
    <div style={{
      flex: 1,
      display: 'flex',
      justifyContent: 'center',
      padding: '60px 40px 120px 40px',
      overflow: 'auto'
    }}>
      <div style={{
        maxWidth: 800,
        width: '100%'
      }}>
        {/* Header */}
        <div style={{
          marginBottom: 48,
          textAlign: 'center'
        }}>
          <h1 style={{
            fontSize: 42,
            fontWeight: 700,
            color: '#2c2c2c',
            fontFamily: 'Georgia, "Times New Roman", serif',
            marginBottom: 16,
            letterSpacing: '-0.5px'
          }}>
            <span style={{ fontStyle: 'italic' }}>I</span>nk & <span style={{ fontStyle: 'italic' }}>M</span>emory
          </h1>
          <p style={{
            fontSize: 18,
            color: '#666',
            lineHeight: 1.6,
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
          }}>
            A reflective writing companion that helps you capture thoughts and memories
          </p>
        </div>

        {/* About Section */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={{
            fontSize: 24,
            fontWeight: 600,
            color: '#2c2c2c',
            marginBottom: 16,
            fontFamily: 'Georgia, "Times New Roman", serif'
          }}>
            About the Project
          </h2>
          <p style={{
            fontSize: 16,
            color: '#555',
            lineHeight: 1.8,
            marginBottom: 16,
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
          }}>
            Ink & Memory is an experimental writing tool that brings multiple "voices" to your writing process.
            As you write, AI-powered personas inspired by Disco Elysium provide commentary, insights, and
            alternative perspectives on your thoughts.
          </p>
          <p style={{
            fontSize: 16,
            color: '#555',
            lineHeight: 1.8,
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
          }}>
            The system analyzes your writing in real-time and generates contextual comments from different
            archetypal voices—Logic, Empathy, Drama, Rhetoric, and more. These voices don't just respond
            to what you write; they help you think differently about it.
          </p>
        </section>

        {/* Team Section */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={{
            fontSize: 24,
            fontWeight: 600,
            color: '#2c2c2c',
            marginBottom: 16,
            fontFamily: 'Georgia, "Times New Roman", serif'
          }}>
            The Team
          </h2>
          <div style={{
            background: 'rgba(255, 255, 255, 0.5)',
            border: '1px solid #d0c4b0',
            borderRadius: 8,
            padding: 24
          }}>
            <div style={{ marginBottom: 20 }}>
              <div style={{
                fontSize: 18,
                fontWeight: 600,
                color: '#2c2c2c',
                marginBottom: 4,
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
              }}>
                F2J
              </div>
              <div style={{
                fontSize: 14,
                color: '#666',
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
              }}>
                Creator & Developer
              </div>
            </div>
            <p style={{
              fontSize: 15,
              color: '#555',
              lineHeight: 1.6,
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
            }}>
              A solo developer exploring the intersection of AI, writing tools, and reflective thinking.
            </p>
          </div>
        </section>

        {/* Timeline Section */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={{
            fontSize: 24,
            fontWeight: 600,
            color: '#2c2c2c',
            marginBottom: 24,
            fontFamily: 'Georgia, "Times New Roman", serif'
          }}>
            Development Timeline
          </h2>
          <div style={{ position: 'relative', paddingLeft: 32 }}>
            {/* Timeline line */}
            <div style={{
              position: 'absolute',
              left: 7,
              top: 8,
              bottom: 8,
              width: 2,
              background: '#d0c4b0'
            }} />

            {/* Timeline items */}
            {[
              {
                version: 'v1.0.0',
                date: 'Oct 2025',
                title: 'Project Start',
                description: 'Core writing interface with voice commentary system'
              },
              {
                version: 'v1.1.0',
                date: 'Oct 2025',
                title: 'Voice Customization',
                description: 'Added settings panel for customizing voice personas'
              },
              {
                version: 'v1.2.0',
                date: 'Oct 2025',
                title: 'Energy Pool System',
                description: 'Introduced weighted character counting and energy-based triggering'
              },
              {
                version: 'v1.3.0',
                date: 'Oct 2025',
                title: 'Calendar & Analysis',
                description: 'Added calendar view for memory browsing and analysis tools'
              }
            ].map((item, index) => (
              <div key={index} style={{
                position: 'relative',
                marginBottom: 32,
                paddingLeft: 8
              }}>
                {/* Timeline dot */}
                <div style={{
                  position: 'absolute',
                  left: -28,
                  top: 4,
                  width: 10,
                  height: 10,
                  borderRadius: 5,
                  background: '#2c2c2c',
                  border: '2px solid #f8f0e6'
                }} />

                <div style={{
                  fontSize: 12,
                  color: '#888',
                  marginBottom: 4,
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                }}>
                  {item.date} • {item.version}
                </div>
                <div style={{
                  fontSize: 16,
                  fontWeight: 600,
                  color: '#2c2c2c',
                  marginBottom: 4,
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                }}>
                  {item.title}
                </div>
                <div style={{
                  fontSize: 14,
                  color: '#666',
                  lineHeight: 1.5,
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                }}>
                  {item.description}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Links Section */}
        <section style={{ marginBottom: 0 }}>
          <h2 style={{
            fontSize: 24,
            fontWeight: 600,
            color: '#2c2c2c',
            marginBottom: 16,
            fontFamily: 'Georgia, "Times New Roman", serif'
          }}>
            Links
          </h2>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <a
              href="https://github.com/shuxueshuxue/ink-and-memory"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '12px 20px',
                background: 'rgba(255, 255, 255, 0.5)',
                border: '1px solid #d0c4b0',
                borderRadius: 8,
                textDecoration: 'none',
                color: '#2c2c2c',
                fontSize: 15,
                fontWeight: 500,
                transition: 'all 0.2s',
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.8)';
                e.currentTarget.style.borderColor = '#b0a490';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.5)';
                e.currentTarget.style.borderColor = '#d0c4b0';
              }}
            >
              <svg height="18" width="18" viewBox="0 0 16 16" fill="currentColor">
                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path>
              </svg>
              GitHub Repository
            </a>
          </div>
        </section>

        {/* Bottom spacer */}
        <div style={{ height: 80 }} />
      </div>
    </div>
  );
}
