// Six broken reminder services - each with one realistic bug. A good check rejects every one.
// (Not a test file: the checker imports it.)
import {
  CHECK_EVERY_MS,
  REMIND_AFTER_MS,
  type CreateReminderService,
} from '../../exercises/testing/reminders.js';

interface Flaws {
  cutoffOffsetMs?: number;
  neverMark?: boolean;
  markBeforeSend?: boolean;
  stopIgnored?: boolean;
  fixedRecipient?: string;
  everyMs?: number;
}

function brokenService(flaws: Flaws): CreateReminderService {
  return ({ orders, mailer }) => {
    let timer: ReturnType<typeof setInterval> | undefined;
    async function check(): Promise<void> {
      const due = await orders.dueForReminder(Date.now() - REMIND_AFTER_MS + (flaws.cutoffOffsetMs ?? 0));
      for (const order of due) {
        try {
          if (flaws.markBeforeSend) await orders.markReminded(order.id);
          await mailer.send({
            to: flaws.fixedRecipient ?? order.customerEmail,
            template: 'payment-reminder',
            orderId: order.id,
          });
          if (!flaws.neverMark && !flaws.markBeforeSend) await orders.markReminded(order.id);
        } catch {
          // swallowed, like the real one
        }
      }
    }
    return {
      start() {
        timer ??= setInterval(() => void check(), flaws.everyMs ?? CHECK_EVERY_MS);
      },
      stop() {
        if (flaws.stopIgnored) return;
        clearInterval(timer);
        timer = undefined;
      },
    };
  };
}

export const reminderMutants: { bug: string; create: CreateReminderService }[] = [
  {
    bug: 'reminds one millisecond late (misses the 30-minute boundary)',
    create: brokenService({ cutoffOffsetMs: -1 }),
  },
  {
    bug: 'never marks orders reminded (sends again every minute)',
    create: brokenService({ neverMark: true }),
  },
  {
    bug: 'marks before sending (a failed send is never retried)',
    create: brokenService({ markBeforeSend: true }),
  },
  { bug: 'stop() does not clear the interval', create: brokenService({ stopIgnored: true }) },
  {
    bug: 'sends every reminder to a debug address',
    create: brokenService({ fixedRecipient: 'qa@sandpay.example' }),
  },
  {
    bug: 'checks every 5 minutes instead of every minute',
    create: brokenService({ everyMs: 5 * CHECK_EVERY_MS }),
  },
];
