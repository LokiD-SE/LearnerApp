package learnerapp.framework;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Serves the practice shop's static files on a free local port, using the HTTP server built into the
 * JDK - no extra dependency, nothing to install.
 *
 * <p>Added because the tests must not depend on a shop someone remembered to start: each test class
 * starts its own, on a port nothing else uses.
 */
public final class ShopServer implements AutoCloseable {

  private static final Map<String, String> TYPES =
      Map.of(
          "html", "text/html; charset=utf-8",
          "css", "text/css; charset=utf-8",
          "js", "text/javascript; charset=utf-8");

  private final HttpServer server;
  private final ExecutorService executor;
  private final Shop shop;

  private ShopServer(HttpServer server, ExecutorService executor) {
    this.server = server;
    this.executor = executor;
    this.shop = new Shop("http://127.0.0.1:" + server.getAddress().getPort() + "/");
  }

  /** Starts serving {@code root} on a free port of the loopback interface. */
  public static ShopServer start(Path root) throws IOException {
    if (!Files.isRegularFile(root.resolve("index.html"))) {
      throw new IllegalStateException(
          "No shop at " + root + " - run the tests from practice/framework or set -Dshop.dir");
    }
    HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    ExecutorService executor = Executors.newFixedThreadPool(4);
    server.setExecutor(executor);
    server.createContext("/", exchange -> serve(root, exchange));
    server.start();
    return new ShopServer(server, executor);
  }

  public Shop shop() {
    return shop;
  }

  private static void serve(Path root, HttpExchange exchange) throws IOException {
    try {
      String path = URLDecoder.decode(exchange.getRequestURI().getPath(), StandardCharsets.UTF_8);
      Path file = root.resolve(path.equals("/") ? "index.html" : path.substring(1)).normalize();
      if (!"GET".equals(exchange.getRequestMethod())
          || !file.startsWith(root)
          || !Files.isRegularFile(file)) {
        exchange.sendResponseHeaders(404, -1);
        return;
      }
      String name = file.getFileName().toString();
      String type = TYPES.getOrDefault(name.substring(name.lastIndexOf('.') + 1), "application/octet-stream");
      byte[] body = Files.readAllBytes(file);
      exchange.getResponseHeaders().set("Content-Type", type);
      exchange.getResponseHeaders().set("Cache-Control", "no-store");
      exchange.sendResponseHeaders(200, body.length);
      try (OutputStream out = exchange.getResponseBody()) {
        out.write(body);
      }
    } finally {
      exchange.close();
    }
  }

  @Override
  public void close() {
    server.stop(0);
    executor.shutdownNow();
  }
}
