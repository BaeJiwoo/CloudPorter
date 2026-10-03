var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

app.MapGet("/", () => new { message = "Hello Deploy" });
app.MapGet("/health", () => new { status = "ok" });
app.MapPost("/echo", (EchoRequest request) =>
    request.Message is null
        ? Results.BadRequest(new { error = "message must be a string" })
        : Results.Ok(new { received = request.Message }));

app.Run();

record EchoRequest(string? Message);
