package learnerapp.concurrency;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

/**
 * Reference solution - submit everything first, then collect the futures in submission order (get()
 * waits for each). ExecutionException wraps the check's own exception: unwrap it. Shut the pool down in
 * finally, or its threads outlive the call.
 */
public final class ParallelChecks {

  private ParallelChecks() {}

  public static List<String> runAll(List<Callable<String>> checks, int threads) {
    ExecutorService pool = Executors.newFixedThreadPool(threads);
    try {
      List<Future<String>> futures = new ArrayList<>();
      for (Callable<String> check : checks) futures.add(pool.submit(check));
      List<String> results = new ArrayList<>();
      for (Future<String> future : futures) {
        try {
          results.add(future.get());
        } catch (ExecutionException e) {
          throw new IllegalStateException("A check failed", e.getCause());
        } catch (InterruptedException e) {
          Thread.currentThread().interrupt();
          throw new IllegalStateException("Interrupted while waiting for the checks", e);
        }
      }
      return results;
    } finally {
      pool.shutdownNow(); // stops checks still running after a failure
    }
  }
}
