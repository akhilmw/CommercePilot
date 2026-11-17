const services = [
  {
    name: "FastAPI + LangGraph",
    description: "Agent orchestration and approval workflow",
  },
  {
    name: "Go MCP service",
    description: "Controlled commerce tools and mutations",
  },
  {
    name: "PostgreSQL",
    description: "Commerce data, workflow state, and audit history",
  },
];

export default function App() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">Week 1 foundation</p>
        <h1>CommercePilot</h1>
        <p className="lede">
          Multi-agent ecommerce intelligence with human-approved execution.
        </p>
      </section>

      <section className="service-grid" aria-label="CommercePilot services">
        {services.map((service) => (
          <article className="service-card" key={service.name}>
            <h2>{service.name}</h2>
            <p>{service.description}</p>
            <span>Scaffolded</span>
          </article>
        ))}
      </section>
    </main>
  );
}

