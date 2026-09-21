// NEXUS Demo File — Java 7 legacy patterns
import java.util.ArrayList;
import java.util.HashMap;
import java.io.FileInputStream;
import java.io.IOException;

public class LegacyApp {
    // Raw types — no generics
    private ArrayList users = new ArrayList();
    private HashMap cache = new HashMap();

    // StringBuffer instead of StringBuilder
    public String buildReport(String[] items) {
        StringBuffer sb = new StringBuffer();
        for (int i = 0; i < items.length; i++) {
            sb.append(items[i]);
            sb.append(", ");
        }
        return sb.toString();
    }

    // System.out.println for logging
    public void processUser(String userId) {
        System.out.println("Processing user: " + userId);
        System.out.println("Cache size: " + cache.size());
    }

    // FileInputStream without try-with-resources
    public void readFile(String path) throws IOException {
        FileInputStream fis = new FileInputStream(path);
        byte[] data = new byte[1024];
        fis.read(data);
        fis.close();
    }

    // Manual null checks instead of Optional
    public String getUserName(String userId) {
        String name = (String) cache.get(userId);
        if (name == null) {
            return "Unknown";
        }
        return name;
    }

    public static void main(String[] args) {
        LegacyApp app = new LegacyApp();
        System.out.println("App started");
    }
}