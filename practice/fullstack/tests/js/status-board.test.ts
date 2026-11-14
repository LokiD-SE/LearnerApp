import { StatusBoard, createAttemptTracker } from '../../exercises/js/status-board.js';

describe('attempt tracker and status board', { tags: ['@exercise'] }, () => {
  describe('createAttemptTracker', () => {
    it('counts failures per order and never goes below zero', () => {
      const tracker = createAttemptTracker(3);
      expect(tracker.remaining('ord_1')).toBe(3);
      expect(tracker.recordFailure('ord_1')).toBe(2);
      expect(tracker.recordFailure('ord_1')).toBe(1);
      expect(tracker.recordFailure('ord_2')).toBe(2);
      expect(tracker.recordFailure('ord_1')).toBe(0);
      expect(tracker.recordFailure('ord_1')).toBe(0);
      expect(tracker.remaining('ord_1')).toBe(0);
      expect(tracker.remaining('ord_2')).toBe(2);
    });

    it('gives every tracker its own counts', () => {
      const a = createAttemptTracker(2);
      const b = createAttemptTracker(2);
      a.recordFailure('ord_1');
      expect(b.remaining('ord_1')).toBe(2);
    });

    it('keeps the counts private', () => {
      const tracker = createAttemptTracker(2);
      tracker.recordFailure('ord_1');
      expect(Object.keys(tracker).sort()).toEqual(['recordFailure', 'remaining']);
      expect(JSON.stringify(tracker)).toBe('{}');
    });
  });

  describe('StatusBoard', () => {
    /** A feed that calls its listener the way real event sources do: as a plain function. */
    const fakeFeed = () => {
      let listener: ((update: { orderId: string; status: string }) => void) | undefined;
      return {
        subscribe(l: typeof listener) {
          listener = l;
        },
        emit(orderId: string, status: string) {
          const call = listener;
          call?.({ orderId, status });
        },
      };
    };

    it('stores the latest status of each order from the feed', () => {
      const feed = fakeFeed();
      const board = new StatusBoard(feed);
      board.start();
      feed.emit('ord_1', 'PENDING');
      feed.emit('ord_2', 'PAID');
      feed.emit('ord_1', 'PAID');
      expect([...board.latest]).toEqual([
        ['ord_1', 'PAID'],
        ['ord_2', 'PAID'],
      ]);
    });

    it('still uses handle to store updates', () => {
      const feed = fakeFeed();
      const board = new StatusBoard(feed);
      const spy = vi.spyOn(board, 'handle');
      board.start();
      feed.emit('ord_1', 'FAILED');
      expect(spy).toHaveBeenCalledWith({ orderId: 'ord_1', status: 'FAILED' });
      expect(board.latest.get('ord_1')).toBe('FAILED');
    });
  });
});
