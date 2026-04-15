import { Agent } from "./agent";

const agent = new Agent();
agent.run("hello").then(console.log);