import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../src/constants/colors';
import HomeTabScreen from './HomeTabScreen';
import SearchScreen from '../SearchScreen';
import ConstitutionTabScreen from './ConstitutionTabScreen';
import NotebookTabScreen from './NotebookTabScreen';
import FlashcardsTabScreen from './FlashcardsTabScreen';
import ProfileTabScreen from './ProfileTabScreen';
import { ROUTES } from '../../src/constants/routes';

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

export default function MainTabs() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="Tabs" options={{ headerShown: false }}>
        {() => (
          <Tab.Navigator
            screenOptions={({ route }) => ({
              headerShown: false,
              tabBarIcon: ({ focused, color, size }) => {
                const icons: Record<string, string> = {
                  [ROUTES.HOME]: focused ? 'home' : 'home-outline',
                  [ROUTES.SEARCH]: focused ? 'search' : 'search-outline',
                  [ROUTES.CONSTITUTION_HUB]: focused ? 'document-text' : 'document-text-outline',
                  [ROUTES.NOTEBOOK]: focused ? 'folder' : 'folder-outline',
                  [ROUTES.FLASHCARDS]: focused ? 'flash' : 'flash-outline',
                  [ROUTES.PROFILE]: focused ? 'person' : 'person-outline',
                };
                return <Ionicons name={icons[route.name] as any} size={size} color={color} />;
              },
              tabBarActiveTintColor: Colors.primary,
              tabBarInactiveTintColor: Colors.textSecondary,
              tabBarStyle: { backgroundColor: Colors.surface, borderTopColor: Colors.border, height: 64, paddingBottom: 8, paddingTop: 8 },
              tabBarLabelStyle: { fontSize: 11, fontWeight: '500' },
            })}
          >
            <Tab.Screen name={ROUTES.HOME} component={HomeTabScreen} />
            <Tab.Screen name={ROUTES.SEARCH} component={SearchScreen} />
            <Tab.Screen name={ROUTES.CONSTITUTION_HUB} component={ConstitutionTabScreen} />
            <Tab.Screen name={ROUTES.NOTEBOOK} component={NotebookTabScreen} />
            <Tab.Screen name={ROUTES.FLASHCARDS} component={FlashcardsTabScreen} />
            <Tab.Screen name={ROUTES.PROFILE} component={ProfileTabScreen} />
          </Tab.Navigator>
        )}
      </Stack.Screen>
    </Stack.Navigator>
  );
}
