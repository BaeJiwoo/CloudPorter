const express = require("express");

const app = express();
const port = Number(process.env.PORT || 8080);

app.use(express.json());
app.get("/", (req, res) => res.json({ message: "Hello Deploy" }));
app.get("/health", (req, res) => res.json({ status: "ok" }));
app.post("/echo", (req, res) => {
  if (typeof req.body?.message !== "string") {
    return res.status(400).json({ error: "message must be a string" });
  }
  res.json({ received: req.body.message });
});

app.listen(port, "0.0.0.0", () => {
  console.log(`Listening on port ${port}`);
});
