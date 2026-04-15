export class Agent {
  async run(input: string): Promise<string> {
    return `Result1: \${input}`;
  }
}