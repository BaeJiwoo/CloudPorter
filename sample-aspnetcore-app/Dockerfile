FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY . .
RUN ["dotnet", "publish", "SampleWeb.csproj", "-c", "Release", "-o", "/out", "--no-self-contained", "/p:UseAppHost=false"]

FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /out .
ENV ASPNETCORE_URLS=http://0.0.0.0:8080
CMD ["dotnet", "SampleWeb.dll"]
